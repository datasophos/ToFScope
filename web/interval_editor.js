// Loaded from a local synced module; no CDN or asset server is required.
export function formatIntervals(intervals) {
  return intervals.length?intervals.map(([low,high])=>`${low.toFixed(4)}–${high.toFixed(4)}`).join(' ∪ ')+' Th':'No intervals';
}
export function sameIntervals(left,right) {
  function canonical(rows) {
    const result=[];
    for(const [low,high] of rows.map(r=>[...r]).sort((a,b)=>a[0]-b[0])) {
      if(result.length && low<=result.at(-1)[1]) result.at(-1)[1]=Math.max(high,result.at(-1)[1]);
      else result.push([low,high]);
    }
    return result;
  }
  return JSON.stringify(canonical(left))===JSON.stringify(canonical(right));
}
export function mountIntervalEditor(root,{send,onSelect=()=>{}}) {
  let selected=null;
  return {
    selectedId(){return selected;},
    sync(state) {
      selected=state.selected_interval_id;
      root.replaceChildren();
      for(const [i,row] of state.draft_windows.entries()) {
        const item=document.createElement('div');item.className='tof-interval-row';item.dataset.intervalId=row.id;
        const choose=document.createElement('button');choose.type='button';choose.dataset.selectInterval=row.id;
        choose.setAttribute('aria-pressed',String(selected===row.id));
        const label=document.createElement('strong');label.textContent=`Interval ${i+1}`;
        const limits=document.createElement('small');limits.textContent=formatIntervals([row.bounds]);
        choose.append(label,limits);
        choose.addEventListener('click',()=>{selected=row.id;onSelect(row);send('interval_select',{id:row.id});});
        const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','Remove interval');
        remove.addEventListener('click',()=>send('interval_remove',{id:row.id}));
        item.append(choose,remove);root.append(item);
      }
      if(!state.draft_windows.length) {
        const empty=document.createElement('small');empty.className='tof-empty-intervals';empty.textContent='No draft intervals';root.append(empty);
      }
    },
    dispose(){root.replaceChildren();}
  };
}
