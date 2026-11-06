# Power BI / FineBI 指标接入说明（未实际集成）

可从DWS/ADS导出CSV/Parquet，或将规范表写入独立PostgreSQL后只读接入。不让商业BI直接扫描raw坏日志。日期表按Asia/Shanghai日键关联，站点表按station_id，设备事实先汇总站日避免多逆变器/组串关联重复。

|BI指标|源字段/表达式|约束|
|---|---|---|
|观测发电|SUM(observed_kwh)|部分覆盖必须同时显示覆盖率|
|单位容量产出|站日observed_kwh/capacity_kwp|不能将各日电站容量SUM后当装机总量|
|PR|SUM(E)/SUM(kWp×POA日辐照)|只在足够覆盖和可靠POA范围汇总|
|在线率|communication_online|不能标为设备可用率|
|可用率|device_availability + availability_status|缺测时只能表示观测部分|
|疑似损失|suspected_loss_kwh|标注模型误差、缺测影响，不作实际挽回收益|
|候选事件|alerts事件ID去重数|不可将重复采样点当故障次数|
|模拟工单|outbox/workorders.json|只读、没有真实派单接口|

Power Query/FineBI中保留null，勿默认填0；筛选时展示有效站日数和指标分母。文件和数据库接入仅提供口径映射，未安装、登录或宣称已完成商业BI集成。
