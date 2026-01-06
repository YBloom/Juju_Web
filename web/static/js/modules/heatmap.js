
let heatmapChart = null;
let currentYear = 2025;

export async function loadHeatmap() {
    const chartEl = document.getElementById('heatmap-chart');
    if (!chartEl) {
        setTimeout(() => {
            if (document.getElementById('heatmap-chart')) loadHeatmap();
        }, 100);
        return;
    }

    if (heatmapChart) {
        heatmapChart.dispose();
    }

    heatmapChart = echarts.init(chartEl);
    heatmapChart.showLoading({
        text: '正在描绘艺廊...',
        color: '#637E60',
        textColor: '#637E60',
        maskColor: 'rgba(255, 255, 255, 0.8)',
    });

    try {
        const response = await fetch(`/api/analytics/heatmap?year=${currentYear}`);
        const result = await response.json();

        const totalEl = document.getElementById('hm_total');
        if (totalEl) totalEl.innerText = result.total.toLocaleString();

        const peakEl = document.getElementById('hm_peak');
        if (peakEl) peakEl.innerText = result.peak;

        renderChart(result.data, result.peak);
        heatmapChart.hideLoading();

        bindYearSelector();

    } catch (err) {
        console.error("Failed to load heatmap:", err);
        heatmapChart.hideLoading();
        chartEl.innerHTML = `<div style="text-align:center; padding:50px; color:#888;">无法加载展品。<br>${err.message}</div>`;
    }
}

function renderChart(data, maxVal) {
    // Sage Green Palette (Light to Dark)
    // #F4F6F4 (Bg match), #E0EBE0 (Lightest), #B8CBB8, #8DA88D, #637E60 (Primary), #4A6347 (Dark)
    const RANGE_COLORS = ['#F4F6F4', '#DDE6DD', '#B2C5B2', '#7A9A7A', '#637E60', '#3D543A'];
    const BG_COLOR = '#FFFFFF';

    const isMobile = window.innerWidth < 768;
    const visualMax = maxVal > 0 ? Math.ceil(maxVal * 0.85) : 50;

    const dayLabel = {
        nameMap: 'cn',
        color: '#9CA3AF', // Gray-400
        firstDay: 1,
        fontFamily: 'Inter, sans-serif'
    };
    const monthLabel = {
        nameMap: 'cn',
        color: '#6B7280', // Gray-500
        fontFamily: 'Outfit, sans-serif',
        fontWeight: 'bold'
    };

    const option = {
        backgroundColor: BG_COLOR,
        tooltip: {
            padding: 0,
            backgroundColor: 'transparent',
            borderColor: 'transparent',
            borderWidth: 0,
            extraCssText: 'box-shadow: none;',
            formatter: (p) => {
                const date = p.value[0];
                const count = p.value[1];
                // Clean white card style with shadow
                return `
                <div style="
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(8px);
                    padding: 12px 16px;
                    border-radius: 12px;
                    border: 1px solid rgba(99, 126, 96, 0.1);
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
                    font-family: 'Inter', sans-serif;
                ">
                  <div style="color: #6B7280; font-size: 0.75rem; margin-bottom: 4px; font-weight: 500;">
                    ${date}
                  </div>
                  <div style="display: flex; align-items: center; gap: 8px;">
                     <div style="
                        width: 8px; height: 8px; 
                        border-radius: 50%; 
                        background: ${count > 0 ? '#637E60' : '#E5E7EB'};
                     "></div>
                     <div style="font-size: 1.1rem; font-weight: 700; color: #1F2937;">
                        ${count} <span style="font-size: 0.75rem; color: #9CA3AF; font-weight: 400;">场</span>
                     </div>
                  </div>
               </div>`;
            }
        },
        visualMap: {
            min: 0,
            max: visualMax,
            calculable: false,
            orient: isMobile ? 'horizontal' : 'horizontal', // Always horizontal for cleaner look
            left: isMobile ? 'center' : 'center',
            bottom: isMobile ? 10 : 0,
            inRange: { color: RANGE_COLORS },
            textStyle: { color: '#9CA3AF', fontFamily: 'Outfit' },
            itemWidth: 15,
            itemHeight: 15, // Square dots for legend
            align: 'auto'
        },
        calendar: {
            top: 50,
            left: isMobile ? 'center' : 'center',
            right: isMobile ? null : null,
            range: String(currentYear),
            orient: 'horizontal',
            cellSize: isMobile ? [Math.floor(window.innerWidth / 55), Math.floor(window.innerWidth / 55)] : [20, 20],
            splitLine: { show: false },
            itemStyle: {
                borderWidth: 3,
                borderColor: '#FFFFFF',
                color: '#FAFAF8'
            },
            yearLabel: { show: false },
            monthLabel: monthLabel,
            dayLabel: isMobile ? { show: false } : dayLabel
        },
        series: [{
            type: 'heatmap',
            coordinateSystem: 'calendar',
            data: data,
            itemStyle: {
                borderRadius: 4, // More rounded
                shadowBlur: 0,
                shadowColor: 'rgba(0, 0, 0, 0.0)'
            },
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowColor: 'rgba(99, 126, 96, 0.2)',
                    color: '#D9885E' // Accent orange on hover
                }
            }
        }]
    };
    heatmapChart.setOption(option);
}

function bindYearSelector() {
    const selectors = document.querySelectorAll('.year-selector span');
    selectors.forEach(span => {
        span.onclick = () => {
            const year = parseInt(span.innerText);
            if (year !== currentYear) {
                currentYear = year;
                selectors.forEach(s => s.classList.remove('active'));
                span.classList.add('active');

                const title = document.querySelector('.heatmap-meta h2');
                if (title) title.innerText = `${year} 演出时间轴`;

                loadHeatmap();
            }
        };
    });
}

window.addEventListener('resize', () => {
    if (heatmapChart) heatmapChart.resize();
});
