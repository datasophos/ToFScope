import Plotly from 'plotly.js-dist-min';
import type{ChartData,ChartHandle}from'../src/plots/selectedRenderer';
export function mountPlotly(el:HTMLElement,data:ChartData):ChartHandle{
 const update=(d:ChartData)=>{return Plotly.react(el,d.kind==='image'?[{x:d.x,y:d.y,z:d.values,type:'heatmap'}]:[{x:d.x,y:d.series![0].values,type:'scatter',mode:'lines'}],{margin:{l:60,r:20,t:20,b:40},xaxis:{range:d.xRange},yaxis:{range:d.yRange},uirevision:'stable'},{displayModeBar:false,staticPlot:true})};update(data);return{update,resize:()=>Plotly.Plots.resize(el),destroy:()=>Plotly.purge(el),exportImage:()=>''};
}
