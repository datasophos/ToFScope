// Reuse server figures while keeping modal zoom and draft selections local.
export function mountDialogPlot(root,{Plotly,getFigure,prepare,onPick,onError}) {
  const dialog=root.closest('dialog');let mounted=false,disposed=false,queue=Promise.resolve(),start=null;
  function refresh() {
    queue=queue.then(async()=>{
      if(disposed || !dialog.open)return;
      const original=getFigure();if(!original)return;
      const figure=structuredClone(original);prepare(figure);
      figure.layout.autosize=true;delete figure.layout.width;delete figure.layout.height;
      await Plotly.react(root,figure.data,figure.layout,{responsive:true,displaylogo:false,scrollZoom:true,
        modeBarButtonsToRemove:['select2d','lasso2d','drawrect','eraseshape']});
      mounted=true;
    }).catch(error=>onError?.(error.message));
    return queue;
  }
  function down(e){if(e.button===0 && !e.target.closest('.modebar'))start={x:e.clientX,y:e.clientY};}
  function up(e){
    const began=start;start=null;if(!began || Math.hypot(e.clientX-began.x,e.clientY-began.y)>4)return;
    const layout=root._fullLayout;if(!layout)return;
    const rect=root.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top,a=layout.xaxis,b=layout.yaxis;
    if(x<a._offset || x>a._offset+a._length || y<b._offset || y>b._offset+b._length)return;
    const value=a.p2d(x-a._offset);if(Number.isFinite(value))onPick(value,root);
  }
  function cancel(){start=null;}
  root.addEventListener('pointerdown',down,true);root.addEventListener('pointerup',up,true);root.addEventListener('pointercancel',cancel);
  const observer=new ResizeObserver(()=>{if(mounted && dialog.open)void Plotly.Plots.resize(root);});observer.observe(root);
  return {refresh,reset(){if(mounted)return Plotly.relayout(root,{'xaxis.autorange':true,'yaxis.autorange':true});},
    range(bounds){if(mounted)return Plotly.relayout(root,{'xaxis.range':bounds});},
    dispose(){disposed=true;observer.disconnect();root.removeEventListener('pointerdown',down,true);root.removeEventListener('pointerup',up,true);root.removeEventListener('pointercancel',cancel);if(mounted)Plotly.purge(root);}};
}
