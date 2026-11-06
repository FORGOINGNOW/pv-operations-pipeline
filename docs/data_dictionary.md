# 数据契约与指标口径 — SYNTHETIC

所有日期显示为 Asia/Shanghai，存储时间为带偏移 ISO8601 或 UTC TIMESTAMPTZ；raw 保留原表示。北为方位角0°，顺时针，南180°。区域/型号/位置全是虚构。

|层/表|粒度/键|内容与血缘|更新策略|
|---|---|---|---|
|raw/telemetry.jsonl|源行，不保证唯一|schema_version、source_system、message_id、event_time、ingest_time、station_id、inverter_id、sequence_no|只读，按日manifest校验；坏JSON也保留|
|raw/stations.csv|每站每天的档案快照|区域、纬经度、装机/AC额定kW、倾角/方位°、gamma 1/°C、投运、退役、生效起止、虚构型号|生效时间范围关联；当前仅支持每快照每站一条版本|
|raw/weather.csv|站点×5分钟|GHI/DNI/DHI/POA W/m²、环境°C、风速m/s、降雨mm、天气、simulated_sensor质量|不把理想无故障功率写入特征|
|raw/events.log|设备事件|时间、站点、状态、人工核验候选|原文只读；尚未形成完整生命周期事实表|
|ODS|源文件×源行|原文payload、source_file、source_line（从1起）、source_byte（从0起）|原样采集、保留坏行|
|DWD|inverter_id×event_time|规范功率kW/累计kWh、三相V/A、Hz、功率因数、MPPT V/A、温度°C、状态/码/固件/延迟秒、档案和气象、多标签质量、插值mask|按日重建；事件时钟定业务分区；ingest定延迟和去重|
|quarantine|源文件×行+原因|原始payload、错误原因、定位|与DWD去重数对账；超窗可显式回填|
|DWS|station_id×当地日|observed_kwh、estimated_kwh=null、覆盖、在线、观测可用、PR、单位容量产出、合成收入|同日覆盖重算，绝不累计追加|
|features/scored|inverter_id×时间|仅当时可用气象/档案/周期特征；预测kW、残差、偏差、门控、评分来源|依赖数据/模型receipt|
|ADS|station_id×当地日|日预期电量、疑似损失、同行/自身、趋势|按日期替换|
|alerts/outbox|事件/工单稳定ID|证据、版本、候选原因、人工建议、模拟状态转换|确定性重放生成本地状态；不发送外部消息|
|simulation_truth|故障事件|类型、起止、参数、可观测性、重叠信息|只允许生成器写、评价模块读；部署计算不读|

功率是5分钟区间平均的模拟采样，能量采用**采样端点梯形近似**，不是简单累加。每设备分别积分再加总，档案容量按逆变器数分摊；气象/档案 many_to_one 校验防关联乘法。组串尚只有遥测MPPT字段，没有独立组串明细子表。

积分：`Σ(P_i+P_(i+1))/2 × Δt_hours`，仅两个端点都有效且0<Δt≤10分钟。函数支持按当地午夜切分；当前日批处理仅使用日内端点，不外推23:55到24:00，夜间近零时通常无影响，其他情况明确少计未观测边界。DuckDB返回微秒时间必须转纳秒再计算，T15专门回归此边界。

随机缺失/缺测段不插值，不补零；observed_kwh只代表支持区间的观测积分，estimated_kwh未知。累计表清零/物理跳变单独打标，counter_delta支持可配置回绕的边界验证；默认不使用累计差分做主能量来源。

|指标|分子/分母与门槛|
|---|---|
|单位容量产出|观测kWh / 档案kWp；昼间覆盖<0.8时未知|
|PR|E_AC / (kWp × POA日辐照kWh/m² / 1kW/m²)；POA>0.1且覆盖充足；POA传感器仍可能有偏差|
|昼间覆盖|POA≥50且AC有效的设备采样数 / 气象网格预期昼间采样数|
|通信在线|去重有效报文数 / (288×逆变器数)，不等于设备运行|
|设备可用|已观测有效昼间状态running比例；缺测时 availability_status=observed_only，不能推断缺失时刻状态|
|同行偏差|(实际容量归一功率−匹配同行中位数)/同行中位数；少于5个、低辐照、分母≤0.02不可判定|
|自身偏差|当天PR / 严格过去28天健康PR中位数−1；过去有效日<5不可判定|
|疑似损失|max(同期气象预测kWh−观测kWh,0)；含缺测/模型误差，不是可确认设备损失|
|合成收入|观测kWh × 0.45元/kWh；不代表真实电价或结算|

状态/事件不用数值均值聚合；计划检修显式抑制，未观测状态保持不确定。未来工单、潜在理想功率、真值损失、故障类型都不在模型 FEATURES 中。
