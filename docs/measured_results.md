# 实测结果 — 2026-11-06 / SYNTHETIC

环境：Windows 11、Python3.12.4、Git Bash5.3.9；库版本见constraints.txt。用户明确选择本次不用虚拟机。Docker引擎未运行，PostgreSQL/Docker未验证。Ubuntu基线由GitHub Actions实际运行。

|档位|实际日期|理论主网格|raw行数|状态|
|---|---|---:|---:|---|
|demo 8站|2025-01-01至2025-12-31|840,960|835,741|全年链路成功；2194份receipt校验通过|
|full 100站单日|2025-01-01|28,800|28,760|端到端成功，未将其称为百站全年实绩|
|full 100站全年|配置2025全年|10,512,000|未运行|仅提供命令和规划估算|

## 质量与规则

全年对账：输入835,741 = 保留832,995 + 去重730 + 隔离2,016，插值0；对账守恒。缺失网格7,965，不补零。

11–12月冻结测试的事件匹配：TP=32，FP=0，FN=12，Precision=1.0000，Recall=0.7273，F1=0.8421。短故障持续门槛等造成漏检；不包装为生产精度。

点级设备评价只在POA≥100W/m²、AC有效、非检修的可评价观测内计算；该分母与事件级不同。详细样本数、误报站日、延迟、P@K、FP/FN见reports/demo/evaluation.json。

质量评价单独输出quality_evaluation.json，仅覆盖版本化已知调度变异，标签事后由注入计划独立重建；不涵盖所有真实故障和随机缺失。事件级质量评价未实现。

## 模型对比

|模型|测试昼间样本|MAE kW|RMSE kW|按设备容量归一MAE|
|---|---:|---:|---:|---:|
|physical|18253|0.061710|0.246724|0.010624|
|regression|18253|0.068090|0.244788|0.011600|
|capacity_median|18253|0.813314|0.986954|0.125085|

物理基线的MAE优于本次回归模型，回归RMSE略低。仿真本身使用近似物理过程，这会偏向物理基线；不宣称模型行业领先。仅一年季节周期，不作真实衰减或因果维修收益结论。

## 资源与运行时间

初次全年生成步骤体实测77.65秒。最终派生物复核运行的步骤体耗时合计965.00秒（16.08分钟），其中raw为365个已生成分区的校验复用；**不等于从零冷启动整条链路的墙钟耗时**，不含解释器启动、校验哈希及Shell开销。

最大步骤结束时RSS采样207.84MiB，**不是峰值内存**。所列raw/ODS/DWD/features/scored/ADS合计758.24MiB，其他报告/模型/状态未包含。每步资源明细见performance.json。

full全年doctor采用每原始行1100字节估算raw约10.77GiB；建议预留25GiB项目空间及至少4GiB可用内存只是规划建议，未实测百站全年耗时或峰值，不外推十万站。

## 可复制命令（PowerShell）

```powershell
Set-Location 'E:\数据分析\pv-operations-pipeline'
& 'D:\SoftWare\RealApp\Git\Git\bin\bash.exe' scripts/90_demo.sh --config configs/smoke.yaml --run-id smoke
& 'D:\SoftWare\RealApp\Git\Git\bin\bash.exe' scripts/backfill.sh --config configs/demo.yaml --run-id demo-year
& 'D:\SoftWare\RealApp\Git\Git\bin\bash.exe' scripts/backfill.sh --config configs/full.yaml --run-id full-year
```

恢复/重试/锁/幂等证据：reports/evidence/recovery.json；迟到回填与raw校验失败保护：late-backfill.json；年度单位/主键/特征契约：contracts-demo.json。测试50项通过，Bash语法和Ubuntu ShellCheck/端到端均实测通过；CI链接和commit在最终交付消息中确认。

HTML：runtime/demo/dashboard/dashboard.html；截图：reports/screenshots/smoke-dashboard.jpg。报告样例：reports/demo；完整未完成/未验证清单见acceptance.md。
