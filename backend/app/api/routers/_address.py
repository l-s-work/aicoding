"""
收货地址路由：CRUD、设为默认
"""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func, update

from app.api.deps import DatabaseSession, CurrentUser
from app.db.models import UserAddress
from app.schemas.address_schema import (
    AddressCreate, AddressUpdate, AddressResponse
)

router = APIRouter(prefix="/addresses", tags=["收货地址"])


@router.post("", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    address_data: AddressCreate,
    db: DatabaseSession,
    current_user: CurrentUser
):
    """
    创建收货地址
    
    - 最多保存5个地址
    - 第一个地址自动设为默认
    """
    # 检查地址数量限制
    count_result = await db.execute(
        select(func.count()).select_from(UserAddress).where(
            UserAddress.user_id == current_user.id
        )
    )
    count = count_result.scalar()
    
    if count >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="最多保存5个收货地址"
        )
    
    # 如果是第一个地址，自动设为默认
    if count == 0:
        address_data.is_default = 1
    
    # 如果新地址要设为默认，取消其他默认地址
    if address_data.is_default == 1:
        await db.execute(
            update(UserAddress)
            .where(UserAddress.user_id == current_user.id)
            .values(is_default=0)
        )
    
    address = UserAddress(
        **address_data.model_dump(),
        user_id=current_user.id
    )
    
    db.add(address)
    await db.commit()
    await db.refresh(address)
    
    return address


@router.get("", response_model=list[AddressResponse])
async def get_addresses(db: DatabaseSession, current_user: CurrentUser):
    """获取当前用户的所有收货地址"""
    result = await db.execute(
        select(UserAddress)
        .where(UserAddress.user_id == current_user.id)
        .order_by(UserAddress.is_default.desc(), UserAddress.created_at.desc())
    )
    addresses = result.scalars().all()
    
    return addresses


@router.get("/{address_id}", response_model=AddressResponse)
async def get_address(address_id: int, db: DatabaseSession, current_user: CurrentUser):
    """获取单个收货地址详情"""
    result = await db.execute(
        select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == current_user.id
        )
    )
    address = result.scalar_one_or_none()
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="收货地址不存在"
        )
    
    return address


@router.put("/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: int,
    address_data: AddressUpdate,
    db: DatabaseSession,
    current_user: CurrentUser
):
    """更新收货地址"""
    result = await db.execute(
        select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == current_user.id
        )
    )
    address = result.scalar_one_or_none()
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="收货地址不存在"
        )
    
    # 更新字段
    update_data = address_data.model_dump(exclude_unset=True)
    
    # 如果要设为默认，取消其他默认地址
    if update_data.get("is_default") == 1:
        await db.execute(
            update(UserAddress)
            .where(UserAddress.user_id == current_user.id)
            .values(is_default=0)
        )
    
    for field, value in update_data.items():
        setattr(address, field, value)
    
    await db.commit()
    await db.refresh(address)
    
    return address


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(address_id: int, db: DatabaseSession, current_user: CurrentUser):
    """
    删除收货地址
    
    - 如果删除的是默认地址，自动将最新的一条设为默认
    """
    result = await db.execute(
        select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == current_user.id
        )
    )
    address = result.scalar_one_or_none()
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="收货地址不存在"
        )
    
    was_default = address.is_default == 1
    
    await db.delete(address)
    await db.commit()
    
    # 如果删除的是默认地址，将最新的一条设为默认
    if was_default:
        result = await db.execute(
            select(UserAddress)
            .where(UserAddress.user_id == current_user.id)
            .order_by(UserAddress.created_at.desc())
            .limit(1)
        )
        latest_address = result.scalar_one_or_none()
        
        if latest_address:
            latest_address.is_default = 1
            await db.commit()


@router.post("/{address_id}/set-default", response_model=AddressResponse)
async def set_default_address(
    address_id: int,
    db: DatabaseSession,
    current_user: CurrentUser
):
    """设置默认收货地址"""
    result = await db.execute(
        select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == current_user.id
        )
    )
    address = result.scalar_one_or_none()
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="收货地址不存在"
        )
    
    # 取消其他默认地址
    await db.execute(
        update(UserAddress)
        .where(UserAddress.user_id == current_user.id)
        .values(is_default=0)
    )
    
    # 设为默认
    address.is_default = 1
    
    await db.commit()
    await db.refresh(address)
    
    return address
