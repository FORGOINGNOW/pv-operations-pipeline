"""Offline HTML embeds aggregate data and Plotly; all raw text enters via textContent."""

import json
from pathlib import Path

import pandas as pd
from plotly.offline import get_plotlyjs

from .core import VERSION, json_write, read_layer


def dashboard(root, c, *_args, **_):
    root = Path(root)
    daily = read_layer(root, "ads")
    if daily.empty:
        raise ValueError("No ADS data")
    events = []
    for p in sorted((root / "alerts").glob("*.json")):
        events.extend(json.loads(p.read_text(encoding="utf-8")))
    evaluation = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))
    orders_path = root / "outbox" / "workorders.json"
    orders = json.loads(orders_path.read_text(encoding="utf-8")) if orders_path.exists() else {}
    payload = json.dumps(
        {
            "daily": json.loads(daily.to_json(orient="records")),
            "events": events,
            "evaluation": evaluation,
            "orders": orders,
            "meta": {
                "timezone": c["timezone"],
                "version": VERSION,
                "data_version": c["data_version"],
                "profile": c["profile"],
                "config_sha256": c["config_sha256"],
            },
        },
        ensure_ascii=False,
    )
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = TEMPLATE.replace("__PLOTLY__", get_plotlyjs()).replace("__DATA__", payload)
    folder = root / "dashboard"
    folder.mkdir(exist_ok=True)
    (folder / "dashboard.html").write_text(html, encoding="utf-8")
    return {"input_count": len(daily), "output_count": 1}


def report(root, c, *_args, **_):
    root = Path(root)
    daily = read_layer(root, "ads")
    daily["period"] = pd.to_datetime(daily.day)
    out = root / "reports"
    out.mkdir(exist_ok=True)
    for kind, freq in [("weekly", "W-SUN"), ("monthly", "M"), ("quarterly", "Q")]:
        df = daily.copy()
        df["period"] = df.period.dt.to_period(freq).astype(str)
        grouped = df.groupby("period").agg(
            observed_kwh=("observed_kwh", "sum"),
            suspected_loss_kwh=("suspected_loss_kwh", "sum"),
            daylight_coverage=("daylight_coverage", "mean"),
            station_days=("station_id", "count"),
        )
        lines = [
            f"# SYNTHETIC DEMO / 合成数据 — {kind}",
            "",
            f"数据版本 {c['data_version']}；模型 {VERSION}；时区 {c['timezone']}。来源：runtime ADS 分区。",
            "",
            "疑似损失受气象、采样与模型偏差影响，不是实际挽回收益。",
            "",
            "|周期|观测电量kWh|疑似损失kWh|平均昼间覆盖|站日数|",
            "|---|---:|---:|---:|---:|",
        ]
        for index, r in grouped.iterrows():
            lines.append(
                f"|{index}|{r.observed_kwh:.2f}|{r.suspected_loss_kwh:.2f}|{r.daylight_coverage:.3f}|{int(r.station_days)}|"
            )
        risks = df.groupby("station_id").suspected_loss_kwh.sum().nlargest(5)
        lines += ["", "重点人工核验候选（按疑似损失，非容量公平排名）：", ""]
        lines += [
            f"- {sid}: {value:.2f} kWh；核验气象、停机日志、档案及计量。" for sid, value in risks.items()
        ]
        lines += ["", "工单来源：outbox/workorders.json。工单均为本地模拟；修复后变化不代表维修因果效果。"]
        (out / f"{kind}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    quality = []
    for p in sorted((root / "quality").glob("*.json")):
        quality.append(json.loads(p.read_text(encoding="utf-8")))
    total = {
        k: sum(r[k] for r in quality)
        for k in ["input_count", "retained", "deduplicated", "quarantined", "filled", "missing_grid_rows"]
    }
    json_write(
        out / "data_quality.json",
        {
            "synthetic": True,
            **total,
            "partitions": len(quality),
            "row_conservation": total["input_count"]
            == total["retained"] + total["deduplicated"] + total["quarantined"],
        },
    )
    e = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))
    (out / "model_validation.md").write_text(
        "# SYNTHETIC 模型与规则验证\n\n```json\n" + json.dumps(e, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    return {"input_count": len(daily), "output_count": 5}


TEMPLATE = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>光伏运营实验室 · SYNTHETIC</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#09131e;color:#dfeaf2;font:15px system-ui,sans-serif}header{padding:28px 4%;border-bottom:1px solid #284050;background:#0e2030}.tag{color:#ffce7b;letter-spacing:2px;font-size:12px}h1{font-size:30px;margin:8px 0}p{color:#a7bbc9}main{max-width:1600px;margin:auto;padding:24px 4%}.controls{display:flex;gap:16px;flex-wrap:wrap;align-items:end}label{display:grid;gap:6px;font-size:12px;color:#a7bbc9}select,input,button{background:#162c3d;color:#e7f3fa;border:1px solid #3c596b;border-radius:6px;padding:10px}button{cursor:pointer}.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:24px 0}.card,.panel{background:#102333;border:1px solid #263e50;border-radius:10px;padding:18px}.card strong{display:block;font:27px ui-monospace,monospace;color:#75dfc2;margin-top:12px}.grid{display:grid;grid-template-columns:1.5fr 1fr;gap:16px}.panel{min-width:0;margin-bottom:16px}.plot{height:330px}h2{font-size:17px;margin-top:0}.tablewrap{overflow:auto;max-height:320px}table{width:100%;border-collapse:collapse;font-size:12px}td,th{text-align:left;padding:10px;border-bottom:1px solid #284050;white-space:nowrap}tr{cursor:pointer}tr:hover{background:#1d394d}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px ui-monospace;color:#c6d8e2}.notice{color:#ffce7b}#empty{padding:15px;color:#ffce7b}footer{padding:20px;color:#92acbd}@media(max-width:850px){.grid{grid-template-columns:1fr}.cards{grid-template-columns:repeat(2,1fr)}}
</style><script>__PLOTLY__</script></head><body><header><div class="tag">合成数据 / SYNTHETIC DEMO · HOUSEHOLD PV</div><h1>光伏运营实验室</h1><p>从设备观测到核验工单 · 同期气象基准与候选异常诊断</p><div id="meta"></div></header><main>
<div class="controls"><label>虚构区域<select id="region"><option value="">全部区域</option></select></label><label>站点<select id="station"><option value="">全部站点</option></select></label><label>开始日期<input type="date" id="start"></label><label>结束日期<input type="date" id="end"></label><button id="export">导出当前表格 CSV</button></div><div id="empty" hidden>无符合筛选的数据 / 数据不足</div>
<div class="cards" id="cards"></div><div class="grid"><section class="panel"><h2>观测电量与模型基准 <small>kWh</small></h2><div id="energy" class="plot"></div></section><section class="panel"><h2>同行与自身偏差 <small>容量/工况归一化</small></h2><div id="deviation" class="plot"></div></section><section class="panel"><h2>数据覆盖与设备可用率</h2><div id="coverage" class="plot"></div></section><section class="panel"><h2>告警热力图 <small>候选事件 / 站日</small></h2><div id="heatmap" class="plot"></div></section></div>
<section class="panel"><h2>异常详情与证据 · 点击行钻取</h2><div class="tablewrap"><table id="alerts"></table></div><pre id="detail">选择一条事件，查看规则版本、偏差、候选原因和人工核验建议。</pre></section>
<section class="panel"><h2>站点日指标 · 缺测保持未知</h2><div class="tablewrap"><table id="daily"></table></div></section>
<div class="grid"><section class="panel"><h2>冻结测试集 · 模型及规则指标</h2><pre id="metrics"></pre></section><section class="panel"><h2>本地模拟工单 · FP/FN 案例</h2><pre id="orders"></pre></section></div>
<p class="notice">疑似损失不是实际挽回收益。通信在线率不能替代设备可用率；可用率仅针对已观测昼间样本，通信缺失部分保持未知。短事件和区域共模异常可能漏检。收益按合成电价计算。</p></main><footer>离线自包含 · Asia/Shanghai · 无真实家庭地址、外部请求或远程控制</footer>
<script id="data" type="application/json">__DATA__</script><script>
'use strict';const D=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);const rows=D.daily;let current=[];
const layout={paper_bgcolor:'#102333',plot_bgcolor:'#102333',font:{color:'#c6d8e2'},margin:{l:55,r:18,t:20,b:50},legend:{orientation:'h',y:1.15},xaxis:{gridcolor:'#263e50'},yaxis:{gridcolor:'#263e50'}};
const num=(v,d=2)=>v==null?'未知':Number(v).toFixed(d);const avg=a=>{a=a.filter(x=>x!=null&&Number.isFinite(x));return a.length?a.reduce((s,v)=>s+v,0)/a.length:null};
const sum=a=>a.filter(x=>x!=null).reduce((s,v)=>s+v,0);const option=(el,v)=>{const o=document.createElement('option');o.value=v;o.textContent=v;el.appendChild(o)};
[...new Set(rows.map(r=>r.region))].sort().forEach(v=>option($('region'),v));const days=[...new Set(rows.map(r=>r.day))].sort();$('start').value=days[0];$('end').value=days.at(-1);
$('meta').textContent=`${D.meta.profile} | ${days[0]} — ${days.at(-1)} | ${D.meta.timezone} | 数据 ${D.meta.data_version} / 模型 ${D.meta.version}`;
function stations(){const old=$('station').value;$('station').replaceChildren();option($('station'),'');$('station').firstChild.textContent='全部站点';[...new Set(rows.filter(r=>!$('region').value||r.region===$('region').value).map(r=>r.station_id))].sort().forEach(v=>option($('station'),v));if([...$('station').options].some(o=>o.value===old))$('station').value=old;}
function table(id,data,cols,click){const el=$(id);el.replaceChildren();const tr=document.createElement('tr');cols.forEach(k=>{const th=document.createElement('th');th.textContent=k;tr.appendChild(th)});el.appendChild(tr);data.forEach(r=>{const tr=document.createElement('tr');cols.forEach(k=>{const td=document.createElement('td');td.textContent=r[k]==null?'未知':typeof r[k]==='number'?num(r[k]):String(r[k]);tr.appendChild(td)});if(click)tr.onclick=()=>click(r);el.appendChild(tr)});}
function render(){current=rows.filter(r=>(!$('region').value||r.region===$('region').value)&&(!$('station').value||r.station_id===$('station').value)&&r.day>=$('start').value&&r.day<=$('end').value);$('empty').hidden=current.length>0;
const stationSet=new Set(current.map(r=>r.station_id)),events=D.events.filter(e=>stationSet.has(e.station_id)&&e.start.slice(0,10)>=$('start').value&&e.start.slice(0,10)<=$('end').value);
$('cards').replaceChildren();[['观测电量 kWh',num(sum(current.map(r=>r.observed_kwh)))],['单位容量产出 kWh/kWp',num(avg(current.map(r=>r.specific_yield)))],['昼间覆盖率',num(100*avg(current.map(r=>r.daylight_coverage)))+'%'],['设备可用率（观测）',num(100*avg(current.map(r=>r.device_availability)))+'%'],['待核验候选事件',String(events.length)]].forEach(([label,value])=>{const c=document.createElement('div');c.className='card';c.textContent=label;const b=document.createElement('strong');b.textContent=value;c.appendChild(b);$('cards').appendChild(c)});
const ds=[...new Set(current.map(r=>r.day))].sort(),groups=ds.map(day=>current.filter(r=>r.day===day));const trace=(name,key,mean=false)=>({x:ds,y:groups.map(g=>mean?avg(g.map(r=>r[key])):sum(g.map(r=>r[key]))),name,mode:'lines',connectgaps:false});
Plotly.react('energy',[trace('观测 kWh','observed_kwh'),trace('同期气象模型 kWh','predicted_kwh')],structuredClone(layout),{responsive:true});Plotly.react('deviation',[trace('同行偏差','peer_deviation',true),trace('自身历史 PR 偏差','self_deviation',true)],{...structuredClone(layout),yaxis:{tickformat:'.0%'}},{responsive:true});Plotly.react('coverage',[trace('昼间覆盖','daylight_coverage',true),trace('通信在线','communication_online',true),trace('设备可用（已观测）','device_availability',true)],{...structuredClone(layout),yaxis:{range:[0,1.05],tickformat:'.0%'}},{responsive:true});
const ss=[...stationSet].sort();Plotly.react('heatmap',[{x:ds,y:ss,z:ss.map(s=>ds.map(d=>events.filter(e=>e.station_id===s&&e.start.slice(0,10)===d).length)),type:'heatmap',colorscale:'YlOrRd',hovertemplate:'%{y}<br>%{x}<br>%{z} 个候选<extra></extra>'}],structuredClone(layout),{responsive:true});
table('alerts',events,['station_id','start','end','rule','confidence'],r=>{$('detail').textContent=JSON.stringify(r,null,2)});table('daily',current,['station_id','day','observed_kwh','specific_yield','pr','daylight_coverage','communication_online','device_availability','confidence']);
$('metrics').textContent=JSON.stringify({comparison:D.evaluation.model_comparison,event:D.evaluation.event,point:D.evaluation.point_equipment,precision_at_k:D.evaluation.precision_at_k,limitation:D.evaluation.limitation},null,2);$('orders').textContent=JSON.stringify({orders:(D.orders.orders||[]).filter(o=>stationSet.has(o.last_event.station_id)),fp:D.evaluation.fp_examples,fn:D.evaluation.fn_examples},null,2);}
stations();$('region').onchange=()=>{stations();render()};['station','start','end'].forEach(id=>$(id).onchange=render);$('export').onclick=()=>{if(!current.length)return;const keys=Object.keys(current[0]);const csv=[keys.join(','),...current.map(r=>keys.map(k=>'"'+String(r[k]??'').replaceAll('"','""')+'"').join(','))].join('\r\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));a.download='SYNTHETIC-pv-filtered.csv';a.click();URL.revokeObjectURL(a.href)};render();
</script></body></html>"""
