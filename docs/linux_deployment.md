# Ubuntu Linux 部署与验收

本项目已在 Ubuntu 24.04 桌面系统、Python 3.12.3 上完成一次本地虚拟机部署。数据均为合成数据，不需要真实电站账号。

## 从源码运行

先安装 Git、Python 3.12 和 venv 支持，然后执行：

```bash
git clone https://github.com/FORGOINGNOW/pv-operations-pipeline.git
cd pv-operations-pipeline
bash deploy/guest_smoke.sh
```

`guest_smoke.sh` 创建项目内虚拟环境，按 constraints.txt 安装依赖，并执行环境检查、pytest、Bash语法检查、7天smoke全链路、SQL与数据契约、失败恢复与迟到回填验证。需要可用的软件包下载网络，首次执行会安装依赖；不会安装系统软件、修改定时任务或真实派单。

本次Ubuntu验收：50项测试通过；Ruff检查、格式检查和pip check通过；smoke、锁冲突、重试、幂等和迟到回填验证通过。此记录不表示所有操作系统和后续提交都已经验证，最新结果以CI和本机运行日志为准。

## 查看看板

```bash
.venv/bin/python -m http.server 8765 --bind 127.0.0.1 \
  --directory runtime/smoke/dashboard
```

在Linux浏览器打开 `http://127.0.0.1:8765/dashboard.html`，Ctrl+C停止服务。在宿主机访问时，可用SSH本机端口转发；连接账号、IP、密钥由使用者自行配置，不放入公共仓库。

## 全年独立重建

```bash
bash scripts/backfill.sh --config configs/demo.yaml \
  --root "$PWD/runtime/demo-linux-fresh" --run-id linux-year
```

该命令生成8站全年数据。此次桌面部署运行的是smoke链路，全年看板使用了已有Windows合成产物的迁移版；没有把迁移描述为Linux重新计算全年。新目录重建后，应把HTTP服务目录改为对应的dashboard目录。

Windows已有receipt使用反斜杠路径，直接迁移到Linux时需保留原记录、规范化outputs相对路径并重新校验文件哈希。依赖签名可能失效，后续执行会重新计算；不要为了跳过任务伪造校验值。新环境优先使用生成器独立重建。

## 凭据与本地配置

runtime、虚拟环境和本机VM控制脚本不提交。SSH私钥、真实.env、真实数据库凭据和真实电站数据不应加入仓库。Docker、PostgreSQL和系统调度模板是可选路径，不属于本次Ubuntu桌面验收范围。
