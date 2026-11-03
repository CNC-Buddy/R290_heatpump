/* Same interpolation and validation contract as curve_math.py. */
export const POINT_LIMITS = {outdoor_min:-30,outdoor_max:35,target_min:-20,target_max:80,step:0.1,max_points:10};
export const ENDPOINT_KEYS = ['t_out_min','t_out_max','t_flow_min','t_flow_max'];
const finite=v=>v!==null&&v!==undefined&&typeof v!=='boolean'&&String(v).trim()!==''&&Number.isFinite(Number(v));
export function pointError(points,limits=POINT_LIMITS){
  if(!Array.isArray(points)||points.length<2||points.length>limits.max_points)return 'Eine Kurve benötigt 2 bis 10 Stützpunkte';
  for(let i=0;i<points.length;i++){
    const p=points[i];
    if(!p||!['outdoor','target'].every(k=>finite(p[k])))return 'Kurvenwerte müssen endliche Zahlen sein';
    for(const k of ['outdoor','target']){
      const v=Number(p[k]);
      if(v<limits[k+'_min']||v>limits[k+'_max'])return 'Stützpunkt außerhalb des zulässigen Temperaturbereichs';
      if(Math.abs(v*10-Math.round(v*10))>1e-8)return 'Stützpunkte benötigen Schritte von 0,1 °C';
    }
    if(i&&Number(p.outdoor)<=Number(points[i-1].outdoor))return 'Außentemperaturen müssen von kalt nach warm eindeutig ansteigen';
  }
  return '';
}
export function pointsOf(values){
  return values.points??[{outdoor:values.t_out_min,target:values.t_flow_max},{outdoor:values.t_out_max,target:values.t_flow_min}];
}
export function curveValue(values,outdoor){
  const points=pointsOf(values);
  if(!finite(outdoor)||pointError(points))return null;
  const x=Number(outdoor);
  if(x<=Number(points[0].outdoor))return Number(points[0].target);
  for(let i=1;i<points.length;i++){
    const a=points[i-1],b=points[i];
    if(x<=Number(b.outdoor))return Number(a.target)+(Number(b.target)-Number(a.target))*(x-Number(a.outdoor))/(Number(b.outdoor)-Number(a.outdoor));
  }
  return Number(points.at(-1).target);
}
export function insertPoint(points){
  if(pointError(points)||points.length>=POINT_LIMITS.max_points)return null;
  let index=0,span=0;
  for(let i=1;i<points.length;i++)if(Number(points[i].outdoor)-Number(points[i-1].outdoor)>span){index=i;span=Number(points[i].outdoor)-Number(points[i-1].outdoor);}
  if(span<0.2-1e-8)return null;
  const outdoor=Math.round((Number(points[index-1].outdoor)+Number(points[index].outdoor))*5)/10;
  const next=points.map(p=>({outdoor:Number(p.outdoor),target:Number(p.target)}));
  next.splice(index,0,{outdoor,target:Math.round(curveValue({points},outdoor)*10)/10});
  return next;
}
