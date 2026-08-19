/**
 * Generate a standalone interactive HTML file with embedded ECharts.
 *
 * The exported HTML bundles ECharts inline so it works fully offline.
 * Chart data is serialized as JSON and rendered on page load.
 */

import type { ChartData } from "./types";

/**
 * Build chart container divs and initialization script for ECharts.
 */
function buildChartScript(chartData: ChartData): { containers: string; initScript: string } {
  const containers: string[] = [];
  const inits: string[] = [];

  // Dashboard
  if (chartData.dashboard) {
    containers.push('<div class="chart-card"><h3>信号仪表盘</h3><div id="chart-dashboard" style="height:220px"></div></div>');
    const sig = chartData.dashboard.signal;
    const sigColor = sig === "Buy" || sig === "Overweight" ? "#089981"
      : sig === "Sell" || sig === "Underweight" ? "#F23645" : "#787B86";
    const scores = chartData.dashboard.scores;
    const radarData = scores.length > 0
      ? [{ value: scores.map(s => s.value), name: "Dimensions", areaStyle: { color: `${sigColor}22` }, lineStyle: { color: sigColor, width: 2 }, itemStyle: { color: sigColor } }]
      : [];
    const indicators = scores.map(s => ({ name: s.name, max: s.max }));

    inits.push(`
      echarts.init(document.getElementById('chart-dashboard')).setOption({
        animation: true, animationDuration: 1500,
        series: [{
          type: 'gauge', center: ['30%','55%'], radius: '80%', min: 0, max: 100,
          startAngle: 220, endAngle: -40,
          progress: { show: true, width: 14, itemStyle: { color: '${sigColor}' } },
          axisLine: { lineStyle: { width: 14, color: [[1,'#2A2E39']] } },
          axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
          pointer: { show: false }, anchor: { show: false },
          title: { show: true, offsetCenter: [0,'30%'], fontSize: 14, color: '#D1D4DC', fontWeight: 'bold' },
          detail: { valueAnimation: true, offsetCenter: [0,'-5%'], fontSize: 28, fontWeight: 'bold', color: '${sigColor}', formatter: function(){return '${sig}'} },
          data: [{ value: ${chartData.dashboard.confidence}, name: '${chartData.dashboard.confidence.toFixed(0)}% confidence' }]
        }${scores.length > 0 ? `,
        { type: 'radar', center: ['72%','55%'], radius: '45%',
          data: ${JSON.stringify(radarData)},
          indicator: ${JSON.stringify(indicators)},
          shape: 'polygon', splitNumber: 4,
          axisName: { color: '#787B86', fontSize: 11 },
          splitLine: { lineStyle: { color: '#2A2E39' } },
          splitArea: { show: false }, axisLine: { lineStyle: { color: '#363A45' } }
        }` : ''}]
      });`);
  }

  // K-line
  if (chartData.kline) {
    const k = chartData.kline;
    containers.push('<div class="chart-card"><h3>K线图</h3><div id="chart-kline" style="height:350px"></div></div>');
    const volColors = k.ohlc.map((o) => o[1] >= o[0] ? "rgba(8,153,129,0.4)" : "rgba(242,54,69,0.4)");
    inits.push(`
      echarts.init(document.getElementById('chart-kline')).setOption({
        animation: true, animationDuration: 800,
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        grid: [{ left: 60, right: 20, top: 30, height: '55%' }, { left: 60, right: 20, top: '72%', height: '18%' }],
        xAxis: [{ type: 'category', data: ${JSON.stringify(k.dates)}, boundaryGap: true, axisLine: { lineStyle: { color: '#363A45' } }, axisLabel: { color: '#787B86', fontSize: 10 } },
                { type: 'category', gridIndex: 1, data: ${JSON.stringify(k.dates)}, boundaryGap: true, axisLabel: { show: false } }],
        yAxis: [{ scale: true, axisLine: { lineStyle: { color: '#363A45' } }, axisLabel: { color: '#787B86', fontSize: 10 }, splitLine: { lineStyle: { color: '#2A2E39' } } },
                { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, splitLine: { show: false } }],
        dataZoom: [{ type: 'inside', xAxisIndex: [0,1], start: 60, end: 100 }],
        series: [
          { name: 'K-line', type: 'candlestick', data: ${JSON.stringify(k.ohlc)},
            itemStyle: { color: '#089981', color0: '#F23645', borderColor: '#089981', borderColor0: '#F23645' } },
          { name: 'Volume', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: ${JSON.stringify(k.volumes)},
            itemStyle: { color: function(p){return ${JSON.stringify(volColors)}[p.dataIndex]||'rgba(120,123,134,0.3)'} } }
        ]
      });`);
  }

  // MACD
  if (chartData.macd) {
    const m = chartData.macd;
    containers.push('<div class="chart-card"><h3>MACD</h3><div id="chart-macd" style="height:200px"></div></div>');
    const histColors = m.histogram.map(v => v >= 0 ? "rgba(8,153,129,0.7)" : "rgba(242,54,69,0.7)");
    inits.push(`
      echarts.init(document.getElementById('chart-macd')).setOption({
        animation: true, animationDuration: 600,
        tooltip: { trigger: 'axis' },
        legend: { data: ['MACD','Signal','Histogram'], textStyle: { color: '#787B86', fontSize: 11 }, top: 0 },
        grid: { left: 60, right: 20, top: 30, bottom: 30 },
        xAxis: { type: 'category', data: ${JSON.stringify(m.dates)}, axisLine: { lineStyle: { color: '#363A45' } }, axisLabel: { color: '#787B86', fontSize: 10 } },
        yAxis: { scale: true, axisLine: { lineStyle: { color: '#363A45' } }, axisLabel: { color: '#787B86', fontSize: 10 }, splitLine: { lineStyle: { color: '#2A2E39' } } },
        series: [
          { name: 'MACD', type: 'line', data: ${JSON.stringify(m.macd)}, lineStyle: { width: 1.5, color: '#2962FF' }, symbol: 'none' },
          { name: 'Signal', type: 'line', data: ${JSON.stringify(m.signal)}, lineStyle: { width: 1.5, color: '#F7B731' }, symbol: 'none' },
          { name: 'Histogram', type: 'bar', data: ${JSON.stringify(m.histogram.map((v,i) => ({value:v,itemStyle:{color:histColors[i]}})))} }
        ]
      });`);
  }

  // RSI
  if (chartData.rsi) {
    const r = chartData.rsi;
    containers.push('<div class="chart-card"><h3>RSI</h3><div id="chart-rsi" style="height:200px"></div></div>');
    inits.push(`
      echarts.init(document.getElementById('chart-rsi')).setOption({
        animation: true, animationDuration: 800,
        tooltip: { trigger: 'axis' },
        grid: { left: 60, right: 20, top: 20, bottom: 30 },
        xAxis: { type: 'category', data: ${JSON.stringify(r.dates)}, axisLine: { lineStyle: { color: '#363A45' } }, axisLabel: { color: '#787B86', fontSize: 10 } },
        yAxis: { min: 0, max: 100, axisLine: { lineStyle: { color: '#363A45' } }, axisLabel: { color: '#787B86', fontSize: 10 }, splitLine: { lineStyle: { color: '#2A2E39' } } },
        series: [{
          name: 'RSI', type: 'line', data: ${JSON.stringify(r.values)}, symbol: 'none',
          lineStyle: { width: 2, color: '#2962FF' },
          areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(41,98,255,0.25)' }, { offset: 1, color: 'rgba(41,98,255,0.02)' }] } },
          markLine: { silent: true, symbol: 'none', lineStyle: { type: 'dashed', width: 1 }, data: [
            { yAxis: 70, lineStyle: { color: '#F23645' }, label: { formatter: '70', color: '#F23645', fontSize: 10 } },
            { yAxis: 30, lineStyle: { color: '#089981' }, label: { formatter: '30', color: '#089981', fontSize: 10 } }
          ]},
          markArea: { silent: true, data: [
            [{ yAxis: 70, itemStyle: { color: 'rgba(242,54,69,0.06)' } }, { yAxis: 100 }],
            [{ yAxis: 0, itemStyle: { color: 'rgba(8,153,129,0.06)' } }, { yAxis: 30 }]
          ]}
        }]
      });`);
  }

  // Bollinger
  if (chartData.bollinger) {
    const b = chartData.bollinger;
    containers.push('<div class="chart-card"><h3>布林带</h3><div id="chart-boll" style="height:250px"></div></div>');
    inits.push(`
      echarts.init(document.getElementById('chart-boll')).setOption({
        animation: true, animationDuration: 800,
        tooltip: { trigger: 'axis' },
        legend: { data: ['Upper','Middle','Lower','Close'], textStyle: { color: '#787B86', fontSize: 11 }, top: 0 },
        grid: { left: 60, right: 20, top: 30, bottom: 30 },
        xAxis: { type: 'category', data: ${JSON.stringify(b.dates)}, axisLine: { lineStyle: { color: '#363A45' } }, axisLabel: { color: '#787B86', fontSize: 10 } },
        yAxis: { scale: true, axisLine: { lineStyle: { color: '#363A45' } }, axisLabel: { color: '#787B86', fontSize: 10 }, splitLine: { lineStyle: { color: '#2A2E39' } } },
        series: [
          { name: 'Upper', type: 'line', data: ${JSON.stringify(b.upper)}, lineStyle: { width: 1, color: '#F23645', type: 'dashed' }, symbol: 'none' },
          { name: 'Middle', type: 'line', data: ${JSON.stringify(b.middle)}, lineStyle: { width: 1.5, color: '#2962FF' }, symbol: 'none' },
          { name: 'Lower', type: 'line', data: ${JSON.stringify(b.lower)}, lineStyle: { width: 1, color: '#089981', type: 'dashed' }, symbol: 'none' },
          { name: 'Close', type: 'line', data: ${JSON.stringify(b.close)}, lineStyle: { width: 2, color: '#D1D4DC' }, symbol: 'circle', symbolSize: 4, itemStyle: { color: '#D1D4DC' } }
        ]
      });`);
  }

  // Fund Flow
  if (chartData.fundFlow) {
    const f = chartData.fundFlow;
    containers.push('<div class="chart-card"><h3>资金流向</h3><div id="chart-fundflow" style="height:250px"></div></div>');
    inits.push(`
      echarts.init(document.getElementById('chart-fundflow')).setOption({
        animation: true, animationDuration: 600,
        tooltip: { trigger: 'axis' },
        legend: { data: ['Northbound','Main Force','Retail'], textStyle: { color: '#787B86', fontSize: 11 }, top: 0 },
        grid: { left: 60, right: 20, top: 30, bottom: 30 },
        xAxis: { type: 'category', data: ${JSON.stringify(f.dates)}, axisLine: { lineStyle: { color: '#363A45' } }, axisLabel: { color: '#787B86', fontSize: 10, rotate: 30 } },
        yAxis: { axisLine: { lineStyle: { color: '#363A45' } }, axisLabel: { color: '#787B86', fontSize: 10 }, splitLine: { lineStyle: { color: '#2A2E39' } } },
        series: [
          { name: 'Northbound', type: 'bar', stack: 'flow', data: ${JSON.stringify(f.northbound)}, itemStyle: { color: '#2962FF', borderRadius: [2,2,0,0] } },
          { name: 'Main Force', type: 'bar', stack: 'flow', data: ${JSON.stringify(f.mainForce)}, itemStyle: { color: '#FF6D00' } },
          { name: 'Retail', type: 'bar', stack: 'flow', data: ${JSON.stringify(f.retail)}, itemStyle: { color: '#787B86', borderRadius: [0,0,2,2] } }
        ]
      });`);
  }

  return { containers: containers.join("\n"), initScript: inits.join("\n") };
}

/**
 * Convert markdown to simple HTML (lightweight, no dependency).
 */
function mdToHtml(md: string): string {
  return md
    // Headers
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold and italic
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Code blocks
    .replace(/```[\s\S]*?```/g, (m) => `<pre><code>${m.slice(3, -3).replace(/<br\s*\/?>/g, "\n")}</code></pre>`)
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Blockquotes
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    // Horizontal rules
    .replace(/^---+$/gm, '<hr>')
    // Paragraphs (double newline)
    .replace(/\n\n/g, '</p><p>')
    // Line breaks
    .replace(/\n/g, '<br>');
}

/**
 * Build the full standalone HTML document with embedded ECharts.
 */
export function buildExportHtml(
  ticker: string,
  signal: string,
  reportMd: string,
  chartData: ChartData | null | undefined,
  echartsMinJs: string,
): string {
  const sigClass = signal.toLowerCase();

  let chartSection = "";
  let chartInitScript = "";

  if (chartData) {
    const { containers, initScript } = buildChartScript(chartData);
    chartSection = `<div class="charts">${containers}</div>`;
    chartInitScript = initScript;
  }

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>${ticker} 分析报告</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1100px; margin: 0 auto; padding: 40px 20px; background: #131722; color: #D1D4DC; }
    h1, h2, h3, h4 { color: #D1D4DC; border-bottom: 1px solid #363A45; padding-bottom: 8px; margin-top: 24px; }
    h1 { margin-top: 0; }
    a { color: #2962FF; }
    code { background: #1E222D; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
    pre { background: #1E222D; padding: 16px; border-radius: 6px; overflow-x: auto; }
    blockquote { border-left: 3px solid #2962FF; margin: 8px 0; padding-left: 16px; color: #787B86; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; }
    th, td { border: 1px solid #363A45; padding: 8px 12px; text-align: left; }
    th { background: #1E222D; }
    .signal-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .signal-buy { background: rgba(8,153,129,0.2); color: #089981; }
    .signal-overweight { background: rgba(38,166,154,0.2); color: #26A69A; }
    .signal-hold { background: rgba(120,123,134,0.2); color: #787B86; }
    .signal-underweight { background: rgba(239,83,80,0.2); color: #EF5350; }
    .signal-sell { background: rgba(242,54,69,0.2); color: #F23645; }
    .charts { margin-bottom: 32px; }
    .chart-card { background: #1E222D; border: 1px solid #363A45; border-radius: 8px; margin-bottom: 16px; overflow: hidden; }
    .chart-card h3 { font-size: 13px; font-weight: 500; padding: 8px 16px; border-bottom: 1px solid #363A45; margin: 0; }
    .chart-card > div { padding: 8px; }
    .report-content { max-width: 900px; margin: 0 auto; }
    .report-content p { margin: 8px 0; line-height: 1.6; }
    .report-content li { margin: 4px 0 4px 20px; line-height: 1.5; }
  </style>
</head>
<body>
  <h1>${ticker} 分析报告</h1>
  <p>信号: <span class="signal-badge signal-${sigClass}">${signal}</span> | 生成时间: ${new Date().toLocaleString("zh-CN")}</p>
  <hr style="border-color: #363A45;">

  ${chartSection}

  <div class="report-content">
    ${mdToHtml(reportMd)}
  </div>

  <script>${echartsMinJs}</script>
  <script>
    var chartData = ${chartData ? JSON.stringify(chartData) : "null"};
    if (chartData) {
      ${chartInitScript}
    }
  </script>
</body>
</html>`;
}
