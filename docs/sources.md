# 版本、算法与一手资料

查阅日期：2026-11-06。确切本机运行版本见constraints.txt和验收记录；官方网页版本可能随时间更新，不将其等同锁定环境。

- [DuckDB Parquet读写](https://duckdb.org/docs/data/parquet)：COPY与Parquet列投影/过滤。工程用内存DataFrame注册后COPY到同目录临时文件；查询检查另实测EXPLAIN ANALYZE。
- [DuckDB分区写入](https://www.duckdb.org/docs/current/data/partitioning/partitioned_writes)：本工程主动按日期逐批写单文件，避免全宽表一次性驻内存；尚未按区域再分物理目录。
- [scikit-learn HistGradientBoostingRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)：固定random_state，关闭内置随机验证early_stopping，外部按时间划分；缺失数值由训练算法支持，不对全年拟合插补器。
- [scikit-learn时间周期特征示例](https://scikit-learn.org/stable/auto_examples/applications/plot_cyclical_feature_engineering.html)：小时/年内日sin-cos与时间验证思路。本工程的拟合/验证范围由代码显式限定。
- [Sandia PVPMC PVWatts](https://pvpmc.sandia.gov/modeling-guide/2-dc-module-iv/point-value-models/pvwatts/)：1000W/m²、25°C参考下的线性温度功率近似。工程实现是教学简化，并非完整PVWatts或经过现场标定的组件模型。
- [Sandia PVPMC模型指南](https://pvpmc.sandia.gov/modeling-guide/)：太阳位置、平面辐照、温度、IV、系统损耗的分层建模背景。

太阳近似：赤纬`23.44° sin(2π(284+doy)/365)`，时角按当地钟时/经度近似，太阳高度来自球面三角；朝南倾斜面的入射近似再乘方位偏差cos，POA由直射、各向同性散射和0.2地面反照率组成。**没有方程时、精确折射、地形遮挡、完整任意朝向太阳方位或光谱模型**，因此不适合真实设计、结算或收益承诺。温升随POA升高、风速降低而增大；γ=-0.0035/°C只是合成参数。

Python代码MIT；NumPy/pandas/scikit-learn/Plotly/DuckDB/PyYAML/psutil等第三方各自许可证继续适用，许可证元数据由包发行版提供。内嵌Plotly JS保留其发行内容和许可证头；没有复制第三方照片、图标或真实气象数据。文档链接是来源，不是将外部模型准确性背书给本简化仿真。
