# 场景覆盖矩阵 — SYNTHETIC / 不穷尽实际故障

状态严格区分“生成器代理”“数据变异fixture”“未实现”。业务故障代理是功率/状态/传感器观测影响，不是完整电路因果模型。场景名仅在独立真值和生成配置中，部署模型不读取。

|编号/场景|配置/注入与字段|策略/检测预期|fixture/测试|状态|
|---|---|---|---|---|
|Q01 seconds|quality.CASES；mutate；simulate站6第115采样点按日轮转|转换到UTC/kW/kWh；保留单位转换标签|test_scenarios T16[seconds]|已实现变异；全年演示轮转|
|Q02 milliseconds|quality.CASES；mutate；simulate站6第115采样点按日轮转|转换到UTC/kW/kWh；保留单位转换标签|test_scenarios T16[milliseconds]|已实现变异；全年演示轮转|
|Q03 timezone_equivalent|quality.CASES；mutate；simulate站6第115采样点按日轮转|转换到UTC/kW/kWh；保留单位转换标签|test_scenarios T16[timezone_equivalent]|已实现变异；全年演示轮转|
|Q04 clock_drift|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[clock_drift]|已实现变异；全年演示轮转|
|Q05 illegal_date|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[illegal_date]|已实现变异；全年演示轮转|
|Q06 cross_day|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[cross_day]|已实现变异；全年演示轮转|
|Q07 future_clock|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[future_clock]|已实现变异；全年演示轮转|
|Q08 irregular|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[irregular]|已实现变异；全年演示轮转|
|Q09 empty|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[empty]|已实现变异；全年演示轮转|
|Q10 null|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[null]|已实现变异；全年演示轮转|
|Q11 nan|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[nan]|已实现变异；全年演示轮转|
|Q12 inf|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[inf]|已实现变异；全年演示轮转|
|Q13 invalid_number|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[invalid_number]|已实现变异；全年演示轮转|
|Q14 missing_field|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[missing_field]|已实现变异；全年演示轮转|
|Q15 added_field|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[added_field]|已实现变异；全年演示轮转|
|Q16 renamed_field|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[renamed_field]|已实现变异；全年演示轮转|
|Q17 watts|quality.CASES；mutate；simulate站6第115采样点按日轮转|转换到UTC/kW/kWh；保留单位转换标签|test_scenarios T16[watts]|已实现变异；全年演示轮转|
|Q18 watt_hours|quality.CASES；mutate；simulate站6第115采样点按日轮转|转换到UTC/kW/kWh；保留单位转换标签|test_scenarios T16[watt_hours]|已实现变异；全年演示轮转|
|Q19 negative|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[negative]|已实现变异；全年演示轮转|
|Q20 spike|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[spike]|已实现变异；全年演示轮转|
|Q21 counter_reset|quality.CASES；mutate；simulate站6第115采样点按日轮转|计数器打标；主能量仍使用功率积分，不拼接表底|test_scenarios T16[counter_reset]|已实现变异；全年演示轮转|
|Q22 unknown_id|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[unknown_id]|已实现变异；全年演示轮转|
|Q23 unknown_inverter|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[unknown_inverter]|已实现变异；全年演示轮转|
|Q24 status_conflict|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[status_conflict]|已实现变异；全年演示轮转|
|Q25 sensor_stuck|quality.CASES；mutate；simulate站6第115采样点按日轮转|卡死仅为fixture；漂移可提示电压候选，不宣称唯一诊断|test_scenarios T16[sensor_stuck]|已实现变异；全年演示轮转|
|Q26 sensor_drift|quality.CASES；mutate；simulate站6第115采样点按日轮转|卡死仅为fixture；漂移可提示电压候选，不宣称唯一诊断|test_scenarios T16[sensor_drift]|已实现变异；全年演示轮转|
|Q27 late_retransmit|quality.CASES；mutate；simulate站6第115采样点按日轮转|normalize隔离或规范化，保留原文；不保证根因可辨|test_scenarios T16[late_retransmit]|已实现变异；全年演示轮转|
|B01 shading|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B02 soiling|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B03 snow|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B04 degradation|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|线性幅度随年内日演示；EWMA适用条件有限，不是真实长期衰减识别|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B05 string_failure|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B06 mppt_fault|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B07 trip|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B08 overtemperature|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B09 efficiency_loss|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B10 grid_outage|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B11 overvoltage|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B12 frequency|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B13 curtailment|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B14 planned_maintenance|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|maintenance状态抑制，正常负对照|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B15 meter_bias|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|物理残差持续规则可能检出；同行/自身提供佐证，不能区分相同功率影响的原因|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|B16 sensor_bias|simulate.FAULTS；站0/1每周前3日轮转；AC/POA/状态/电压/Hz|POA偏高可能引发物理模型误报，需人工传感器核验|T07/T12正常对照；evaluate点级及事件级回测|已实现简化观测代理，未逐类型断言召回|
|X01 随机缺失/连续缺测|逐行0.001丢失；站2 125–139缺报|不补零；低覆盖可见；不能从缺报推断停机|T07|已实现|
|X02 完全/冲突重复与乱序|站3第112/113；确定性shuffle|ingest_time→sequence_no→source_line最后者胜出；唯一性与对账|T07/verify_sql|已实现|
|X03 坏JSON/截断|每日尾行不完整JSON|quarantine保留行号字节|T07|已实现|
|X04 BOM/编码|collect使用utf-8-sig与替换标记|BOM可解码；任意旧编码转码未实现|T04/源码|部分|
|X05 夜间/区域云雨/削顶/朝向容量|季节日照、共享平滑云、逆变器上限、档案|正常对照，夜间不触发，容量归一|T08/T12|已实现|
|X06 档案过期|valid_from/valid_to过滤|隔离并行数守恒；无当日多版映射|T14|已实现单版本边界|
|X07 计数器回绕|core.counter_delta rollover参数|需已知计数器上限；默认主链路不自动猜测|T03|函数已实现，仿真未注入|
|X08 多逆变器|inverters=2..8；容量分摊|分设备积分再汇总站点，不乘天气行数|T13|已实现|
|X09 整日文件缺失|缺源文件时collect失败|不成功提交分区，不声称设备全天0发电|恢复验证|失败路径有，未独立周期性注入|
|X10 交叠/长短故障|设备故障可与随机丢失/坏值交叠；15分钟或4小时|短故障可能被持续门槛漏掉；gap切断|T09/评价FN|已实现部分；多设备业务故障叠加未实现|
|X11 安装/复机/更换/退役生命周期|events.log和档案仅有部分字段|无法据现有文本还原完整生命周期|无|未实现完整事实表|
|X12 映射变更/容量朝向错误/气象站错配|档案/天气安全关联但未主动生成错误配置|可能表现PR/残差异常，不可唯一归因|无|未实现注入|
|X13 收益结算延迟/电价错误|仅合成固定电价0.45|无真实结算系统，不可诊断结算延迟|无|未实现|
|X14 组串独立子表|仅MPPT遥测字段|组串故障目前是观测功率代理|无|未实现独立子表|
|X15 阈值调优与冷却|恢复2个正常样本；本地工单合并|-20%演示预设；无显式冷却定时器/验证集阈值选择|T09/评价敏感性|部分|
|X16 电气危险|过压/频率打标与候选建议|仅转专业人工核验，无控制/维修操作|T06|已实现提示边界|

质量标签是多标签；解析失败、可信电气异常、测量不确定性分别处理。低效候选不是因果鉴定。没有适用传感器的项保留“未实现/无法判断”，不伪造全覆盖。
