# Shell 学习与面试演示

Shell负责过程，Python/SQL负责计算。按顺序阅读 scripts/lib/common.sh → 90_demo.sh → verify_recovery.py。

- `set -Eeuo pipefail`：继承ERR、错误退出、未定义变量报错、管道任一失败导致非零。ERR在if/while条件、`!`、`&&/||`等上下文有例外，不能当全局异常保证。run_step刻意放if里立即捕获退出码，再将结果返回；不以tee吞错。
- `"$var"`和`"${array[@]}"`分别保留带空格路径和独立参数。`${BASH_SOURCE[0]}`定位脚本；`cd --`固定工作目录；不用eval，不source YAML，用safe_load。
- `>`覆盖stdout，`>>`追加；`2>&1`合并stderr。`command > logfile 2>&1`后立即检查`$?`。项目CLI输出JSON，可独立保存stderr以区分诊断。
- 管道用于文本转换，`grep`查普通文本，`awk`可做列级计数，`jq`/Python解析JSON；不要grep“success”就认定成功。
- 退出0成功，1配置/计算失败，2参数不合法，73锁冲突，75临时源不可用。Linux `chmod +x scripts/*.sh`与Git执行位不同；仓库记录100755，Shell文件LF。
- `mkdir`用于便携锁，`mktemp`创建run临时目录，trap只清本run scratch。flock不是Windows Git Bash基线依赖；timeout/cron/GNU date不是所有平台都有。

```bash
# Bash语法检查，不执行
bash -n scripts/lib/common.sh
# 非JSON日志文本可grep
grep -n 'PIPELINE_SUCCESS' demo-console.txt
# 结构化日志必须解析JSON
jq -s 'group_by(.step)|map({step:.[0].step,seconds:map(.duration)|add})' runtime/demo/logs/demo-year.jsonl
# 不依赖jq的等价入口
.venv/bin/python -c 'import json,pathlib; print([json.loads(x) for x in pathlib.Path("runtime/demo/logs/demo-year.jsonl").read_text().splitlines()][-1])'
# 基本环境/权限/磁盘与进程
command -v python3
ls -l scripts/90_demo.sh
df -h .
du -sh runtime/demo
ps -ef
```

把`PV_FAIL_STEP=clean`失败→查看无watermark→取消故障重跑→receipt校验跳过的过程作为Shell展示重点。真实恢复证据由脚本断言生成，而不是手写“恢复成功”。
