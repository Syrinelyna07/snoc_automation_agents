import { useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';

export default function ChartCanvas({ type, data, options }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    Chart.defaults.font.family = 'Inter, sans-serif';
    Chart.defaults.color = '#64748B';
    chartRef.current = new Chart(canvasRef.current, { type, data, options });
    return () => chartRef.current && chartRef.current.destroy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.data.labels = data.labels;
    chart.data.datasets.forEach((ds, i) => {
      if (data.datasets[i]) Object.assign(ds, data.datasets[i]);
    });
    chart.update('none');
  }, [data]);

  return <canvas ref={canvasRef}></canvas>;
}
