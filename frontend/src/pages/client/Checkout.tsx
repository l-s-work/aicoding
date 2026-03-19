import { Alert, Typography } from 'antd';
import styled from 'styled-components';

const { Title, Paragraph } = Typography;

const Checkout = () => (
  <ContentWrap>
    <Title level={3}>订单结算</Title>
    <Alert
      type="info"
      showIcon
      message="当前作业版本先完成了商品与订单查询链路，结算创建订单流程可继续在此页完善。"
    />
    <Paragraph style={{ marginTop: 16 }}>
      建议下一步接入：地址选择、订单确认、创建订单接口调用、支付按钮（假支付）联调。
    </Paragraph>
  </ContentWrap>
);

const ContentWrap = styled.div`
  max-width: 960px;
  width: 100%;
  margin: 0 auto;
`;

export default Checkout;
