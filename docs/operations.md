# 运行、部署与排障

## 环境边界

完整目标为 Python3.12/Bash Linux，实际 Ubuntu 验证看 acceptance.md 中的 CI 链接。Windows 入口是 Git Bash，不是系统 bash（WSL）。Shell 设置 PYTHONUTF8/PYTHONIOENCODING，避免原生 Python 输出被 Bash 命令替换误解码。不要在不明目录执行清理。VMware 程序存在不等于已有可登录Linux客机；本次按用户后续指示不使用VM。

新机器先 bootstrap，再 doctor；doctor给出锁定库版本、解释器、理论网格和仅用于规划的raw体积估算。按日生成/处理，回归拟合最多稳定hash抽样120000条；数据库扫描按列投影，不把全量宽表装入内存。full档100站远低于十万站，不能外推实绩。10万站×288=2880万行/日仅为行数算式。

## 锁、提交、恢复

`mkdir .pipeline.lock` 是本地文件系统上的单实例互斥锁，对整个runtime生效，强于同分区锁。记录run_id、pid、host。正常退出/ERR/可捕获中断由EXIT trap释放；断电/SIGKILL不能捕获，须检查owner对应进程确已结束，再只删除该锁目录里的owner.json并rmdir空锁目录。不要自动抢占不明锁。

临时目录由mktemp创建且限制在root/tmp/run_id.*；退出只rmdir该空目录，没有递归rm。每个Parquet/JSON先写同目录.tmp后os.replace，只有所有本步输出成功才写receipt；下游需先有依赖receipt。**多文件输出不是一个文件系统原子事务**：崩溃可能留下尚未receipt提交的部分文件，重跑会覆盖；不能把这些文件视为完成分区。全链路最后更新watermark。Windows不支持完全相同的POSIX信号语义，不声称SIGKILL可自动清锁。

每步signature包含源码摘要、配置摘要、上游receipt内容和回填模式；产物SHA验证后才跳过。Raw文件始终校验不可变，生成配置变更要使用新root。`--force`只重算派生物，不修改raw。当前历史自身基准对其他日期DWS的依赖未逐个编码进单日score signature；补写历史数据后请显式 `--force` 重评分受影响的后续28日。模型依赖整个features receipt集合，回填会触发重新拟合。

只有退出75（暂时故障）重试，最多3次，等待1、2秒。非法配置、坏schema导致步骤失败时直接退出，不盲目重试。坏源行按契约进入quarantine，与整步骤失败区分。错误输出JSON含run_id/step/exit_code，成功日志还含date/attempt/duration/input/output/rss。日志不含凭据；外部Webhook留空不会发送。

```bash
PV_FAIL_STEP=clean bash scripts/90_demo.sh --config configs/smoke.yaml --root runtime/failure-demo --run-id fail
# 预期非零，无watermark、无clean receipt
PV_TRANSIENT_ONCE=clean bash scripts/90_demo.sh --config configs/smoke.yaml --root runtime/failure-demo --run-id resume
bash scripts/90_demo.sh --config configs/smoke.yaml --root runtime/failure-demo --run-id again
```

## Linux容器（可选，状态见验收）

```bash
docker build -f deploy/Dockerfile -t synthetic-pv .
docker run --rm -v pv-runtime:/opt/pv/runtime synthetic-pv --config configs/smoke.yaml
# Compose中的Postgres是显式profile，不会被默认启动
docker compose --env-file .env -f deploy/compose.yaml --profile postgres up -d postgres
docker compose --env-file .env -f deploy/compose.yaml exec -T postgres psql -U pv -d pv < sql/postgresql.sql
```

容器uid10001、无root业务进程；数据库只127.0.0.1映射；只用命名数据卷，避免宿主危险挂载。`.env`不提交，不在命令行打印密码。PostgreSQL文件是示例，不能据其存在宣称已验证。

## 调度

cron和systemd timer二选一，模板在deploy；**不自动安装或启用**。cron设置CRON_TZ和绝对工作目录/解释器；systemd设置Asia/Shanghai日历、User、WorkingDirectory、NoNewPrivileges、只允许runtime写入、journal捕获失败状态。`scheduled.sh`的GNU date仅Linux适用。先做历史回填准备训练数据再调度日批；当前模拟器不是持续接入真实设备，历史演示常用固定日期范围。

## 日志、保留与备份

按run_id生成JSONL，自然分片；默认不自动删除或轮转历史文件。生产化可按本项目绝对路径加logrotate策略并先dry-run。本版本只提供安全列举，不自动清理用户文件：

```bash
find runtime/demo/logs -maxdepth 1 -type f -name '*.jsonl' -mtime +30 -print
du -sh runtime/demo
df -h .
ps -eo pid,etime,rss,args | head
```

保留raw、manifest、模型及manifest、配置、receipt、outbox、evaluation；派生Parquet可从raw重建。备份到新的专用目录，例如 `tar -czf /backup/pv-2025-demo.tar.gz runtime/demo configs constraints.txt`；先列tar目录再解包到新root，运行verify。不覆盖唯一备份。

模型回滚：停止本项目日批并确认锁已释放，将以前整组models目录及manifest复制到**新的runtime副本**，保留当前模型备份，检查schema/features/config版本，再 `--force` 重新score/evaluate/dashboard/report。不要加载来源不明pickle。当前模型manifest记录训练范围，但没有完整跨机器环境签名；升级Python/sklearn需重新训练。

常见排障：退出73检查锁owner；75检查暂时源故障；1检查stderr JSON和首个失败step；quarantine按source_file/line/byte回溯；receipt失败查原始checksum和上游配置。修复后用同一root重跑；run_id可以新建，数据幂等性不依赖run_id固定。
