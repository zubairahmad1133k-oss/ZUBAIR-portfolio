// Dependency-free interactive line chart for the analytics page.
// Data comes from the server as JSON (real database counts only).
(function () {
  var dataNode = document.getElementById('analytics-data');
  var host = document.getElementById('chart-traffic');
  if (!dataNode || !host) return;

  var data = JSON.parse(dataNode.textContent);
  var SERIES = [
    { key: 'page_views', label: 'Page views', color: '#58c9ff' },
    { key: 'visitors', label: 'Unique visitors', color: '#ff4fa3' },
    { key: 'project_views', label: 'Project views', color: '#a78bfa' }
  ];
  var NS = 'http://www.w3.org/2000/svg';
  var W = 720, H = 280, PAD = { l: 42, r: 16, t: 14, b: 30 };
  var n = data.labels.length;
  var plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b;

  var all = [];
  SERIES.forEach(function (s) { all = all.concat(data[s.key]); });
  var max = Math.max.apply(null, all.concat([1]));
  if (max < 4) max = 4;
  max = Math.ceil(max / 4) * 4;

  function px(i) { return PAD.l + (n === 1 ? plotW / 2 : (i * plotW) / (n - 1)); }
  function py(v) { return PAD.t + plotH * (1 - v / max); }
  function el(name, attrs, parent) {
    var node = document.createElementNS(NS, name);
    for (var k in attrs) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }
  function shortDate(iso) {
    var d = new Date(iso + 'T00:00:00Z');
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
  }

  var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Traffic over time' });
  svg.style.width = '100%'; svg.style.height = 'auto'; svg.style.display = 'block';

  // grid + y labels
  for (var g = 0; g <= 4; g++) {
    var v = (max / 4) * g, y = py(v);
    el('line', { x1: PAD.l, x2: W - PAD.r, y1: y, y2: y, stroke: 'rgba(255,255,255,.08)' }, svg);
    var t = el('text', { x: PAD.l - 8, y: y + 4, 'text-anchor': 'end', fill: '#aaa8bb', 'font-size': 11 }, svg);
    t.textContent = Math.round(v);
  }
  // x labels (at most ~6)
  var step = Math.max(1, Math.ceil(n / 6));
  for (var i = 0; i < n; i += step) {
    var tx = el('text', { x: px(i), y: H - 8, 'text-anchor': 'middle', fill: '#aaa8bb', 'font-size': 11 }, svg);
    tx.textContent = shortDate(data.labels[i]);
  }
  // lines + points
  SERIES.forEach(function (s) {
    var pts = data[s.key].map(function (val, idx) { return px(idx) + ',' + py(val); }).join(' ');
    el('polyline', { points: pts, fill: 'none', stroke: s.color, 'stroke-width': 2.5, 'stroke-linejoin': 'round' }, svg);
    if (n <= 45) data[s.key].forEach(function (val, idx) {
      el('circle', { cx: px(idx), cy: py(val), r: 3, fill: s.color }, svg);
    });
  });

  // hover guide + tooltip
  var guide = el('line', { y1: PAD.t, y2: PAD.t + plotH, stroke: 'rgba(255,255,255,.35)', 'stroke-dasharray': '3 3', visibility: 'hidden' }, svg);
  var tip = document.createElement('div');
  tip.className = 'chart-tip'; tip.style.display = 'none';
  var overlay = el('rect', { x: PAD.l, y: PAD.t, width: plotW, height: plotH, fill: 'transparent' }, svg);

  overlay.addEventListener('mousemove', function (event) {
    var rect = svg.getBoundingClientRect();
    var mx = (event.clientX - rect.left) * (W / rect.width);
    var idx = n === 1 ? 0 : Math.round(((mx - PAD.l) / plotW) * (n - 1));
    idx = Math.max(0, Math.min(n - 1, idx));
    guide.setAttribute('x1', px(idx)); guide.setAttribute('x2', px(idx));
    guide.setAttribute('visibility', 'visible');
    tip.innerHTML = '';
    var head = document.createElement('strong'); head.textContent = shortDate(data.labels[idx]);
    tip.appendChild(head);
    SERIES.forEach(function (s) {
      var line = document.createElement('div');
      line.textContent = s.label + ': ' + data[s.key][idx];
      line.style.color = s.color;
      tip.appendChild(line);
    });
    tip.style.display = 'block';
    var left = (px(idx) / W) * rect.width;
    tip.style.left = Math.min(left + 12, rect.width - 150) + 'px';
  });
  overlay.addEventListener('mouseleave', function () {
    guide.setAttribute('visibility', 'hidden'); tip.style.display = 'none';
  });

  host.appendChild(svg);
  host.appendChild(tip);

  var legend = document.getElementById('chart-legend');
  if (legend) SERIES.forEach(function (s) {
    var item = document.createElement('span');
    item.className = 'legend-item';
    var dot = document.createElement('i'); dot.style.background = s.color;
    item.appendChild(dot); item.appendChild(document.createTextNode(s.label));
    legend.appendChild(item);
  });
})();
