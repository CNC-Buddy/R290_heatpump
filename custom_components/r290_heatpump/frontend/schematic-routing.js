// Geometry only: moving a drawn pipe never changes its hydraulic endpoints.
export const equal=(a,b)=>a[0]===b[0]&&a[1]===b[1];
// Saved automatic geometry is independent of unrelated component obstacles.
// Port stubs may extend outside the 0..3600 component-position range.
export function validRoute(route){return Array.isArray(route)&&route.length>=2&&route.length<=256&&route.every(p=>Array.isArray(p)&&p.length===2&&p.every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=-100&&v<=4000))&&route.every((p,i)=>!i||p[0]===route[i-1][0]||p[1]===route[i-1][1]);}
export function retainRoutes(graph,geometry){
  for(const edge of graph.edges){
    const route=geometry?.[edge.id]?.route;
    if(edge.points?.length)delete edge.route;
    else if(validRoute(route))edge.route=route.map(p=>[...p]);
  }
}
export function simplify(points){
  const out=[];
  for(const point of points){
    const p=[...point];if(out.length&&equal(out.at(-1),p))continue;
    while(out.length>1){const a=out.at(-2),b=out.at(-1);if(a[0]===b[0]&&b[0]===p[0]||a[1]===b[1]&&b[1]===p[1])out.pop();else break;}
    if(!out.length||!equal(out.at(-1),p))out.push(p);
  }
  return out;
}
export function orthogonal(points){
  const out=[points[0]];
  for(const p of points.slice(1)){const a=out.at(-1);if(a[0]!==p[0]&&a[1]!==p[1])out.push([p[0],a[1]]);out.push(p);}
  return simplify(out);
}
export function clearSegment(a,b,boxes){
  return !boxes.some(r=>a[0]===b[0]?a[0]>r[0]&&a[0]<r[2]&&Math.max(a[1],b[1])>r[1]&&Math.min(a[1],b[1])<r[3]:a[1]>r[1]&&a[1]<r[3]&&Math.max(a[0],b[0])>r[0]&&Math.min(a[0],b[0])<r[2]);
}
// Exact endpoint coordinates avoid the old grid-snap hooks. Heading is part of
// each search state, so equal-length Manhattan paths prefer few bends.
export function autoRoute(start,end,boxes,startAxis=0,endAxis=0){
  if(equal(start,end))return [start,end];
  if((start[0]===end[0]||start[1]===end[1])&&clearSegment(start,end,boxes))return [start,end];
  const axis=(i)=>[...new Set([0,start[i],end[i],...boxes.flatMap(r=>[Math.max(0,r[i]),Math.min(3900,r[i+2])])])].sort((a,b)=>a-b);
  const xs=axis(0),ys=axis(1),s=[xs.indexOf(start[0]),ys.indexOf(start[1])],t=[xs.indexOf(end[0]),ys.indexOf(end[1])];
  const key=(x,y,h)=>`${x},${y},${h}`,point=(x,y)=>[xs[x],ys[y]],heuristic=(x,y)=>Math.abs(xs[x]-end[0])+Math.abs(ys[y]-end[1]);
  const heap=[],push=v=>{heap.push(v);let i=heap.length-1;while(i){const p=(i-1)>>1;if(heap[p].f<=v.f)break;heap[i]=heap[p];i=p;}heap[i]=v;};
  const pop=()=>{const v=heap[0],last=heap.pop();if(heap.length){let i=0;while(i*2+1<heap.length){let c=i*2+1;if(c+1<heap.length&&heap[c+1].f<heap[c].f)c++;if(heap[c].f>=last.f)break;heap[i]=heap[c];i=c;}heap[i]=last;}return v;};
  const first={x:s[0],y:s[1],h:startAxis,g:0},cost=new Map([[key(...s,startAxis),0]]),previous=new Map();push({...first,f:heuristic(...s)});
  let found=null,iterations=0;
  while(heap.length&&iterations++<150000){
    const at=pop(),k=key(at.x,at.y,at.h);if(at.g!==cost.get(k))continue;
    if(at.x===t[0]&&at.y===t[1]){found=at;break;}
    for(const [dx,dy,h] of [[1,0,0],[-1,0,0],[0,1,1],[0,-1,1]]){
      const x=at.x+dx,y=at.y+dy;if(x<0||y<0||x>=xs.length||y>=ys.length)continue;
      const a=point(at.x,at.y),b=point(x,y);if(!clearSegment(a,b,boxes))continue;
      const g=at.g+Math.abs(a[0]-b[0])+Math.abs(a[1]-b[1])+(h===at.h?0:80)+(x===t[0]&&y===t[1]&&h!==endAxis?80:0),qk=key(x,y,h);
      if(g<(cost.get(qk)??Infinity)){cost.set(qk,g);previous.set(qk,at);push({x,y,h,g,f:g+heuristic(x,y)});}
    }
  }
  // Overlapping components can make routing impossible. Keep endpoints visible;
  // manual handles remain available to resolve such layouts.
  if(!found)return orthogonal([start,end]);
  const route=[];for(let at=found;at;at=previous.get(key(at.x,at.y,at.h)))route.push(point(at.x,at.y));
  return simplify(route.reverse());
}
export function viaPoints(start,end,points,startAxis=0,endAxis=0){
  if(!points.length)return orthogonal([start,end]);
  const first=points[0],last=points.at(-1);
  const head=startAxis===0?[start[0],first[1]]:[first[0],start[1]];
  const tail=endAxis===0?[end[0],last[1]]:[last[0],end[1]];
  return orthogonal([start,head,...points,tail,end]);
}
export function moveSegment(route,index,value){
  if(index<0||index>=route.length-1)throw Error('pipe');
  const points=route.map(p=>[...p]),axis=points[index][0]===points[index+1][0]?0:1;
  points[index][axis]=value;points[index+1][axis]=value;
  // Endpoints here are the fixed port stubs, never the actual component ports.
  const result=simplify([route[0],...points,route.at(-1)]).slice(1,-1);
  if(result.length>16||result.some(p=>p.some(v=>!Number.isFinite(v)||v<0||v>3600)))throw Error('pipe');
  return result;
}
