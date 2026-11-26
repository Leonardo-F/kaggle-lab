#include <bits/stdc++.h>
using namespace std; using I=long long; using W=__int128_t;
struct E{I v,a,b;char o;};
using P=vector<E>;
struct Solver{
 I L; vector<I>s,ts,active; unordered_map<I,E> graph; unordered_set<I> root,known; unordered_map<I,vector<E>> dict; mt19937_64 rng; int width,mode; vector<I> probes,bases,all_values; unordered_map<I,P> memo; unordered_map<I,int> used_at, depdepth; int tick=0;
 Solver(I l,vector<I> ss,vector<I> tt,int w,int m):L(l),s(ss),ts(tt),rng(1909),width(w),mode(m){dict.reserve(200000); for(I x:s){root.insert(x);known.insert(x);active.push_back(x);} for(I a:s)for(I b:s)pair(a,b); seed();}
 void put(W v,I a,I b,char o){if(v<1||v>L||known.count((I)v))return;auto &es=dict[(I)v]; if(es.size()>=3)return;for(auto e:es)if(e.a==a&&e.b==b&&e.o==o)return;es.push_back({(I)v,a,b,o});}
 void pair(I a,I b){put((W)a+b,a,b,'+');put((W)a*b,a,b,'*');if(a>b)put(a-b,a,b,'-');if(b>a)put(b-a,b,a,'-');if(a%b==0)put(a/b,a,b,'/');if(b%a==0)put(b/a,b,a,'/');}
 void add(E e){if(known.count(e.v))return;if(!known.count(e.a)||!known.count(e.b))throw runtime_error("dependency");graph[e.v]=e; ++tick; used_at[e.a]=used_at[e.b]=used_at[e.v]=tick; depdepth[e.v]=1+max(depdepth[e.a],depdepth[e.b]);known.insert(e.v);dict.erase(e.v);for(I a:active)pair(a,e.v);pair(e.v,e.v);active.push_back(e.v);}
 bool has(I v){return known.count(v)||dict.count(v);}
 double pressure(I v){if(root.count(v)||!known.count(v))return 0.; auto it=used_at.find(v);int age=tick-(it==used_at.end()?0:it->second);int d=depdepth[v];return .12*min(2.0,age/64.)*min(4,d);}
 P leaf(I v){if(known.count(v))return {};auto it=dict.find(v);if(it==dict.end())throw runtime_error("missing");auto best=it->second.front();double bc=pressure(best.a)+((best.a==best.b)?0.:pressure(best.b));for(auto e:it->second){double c=pressure(e.a)+(e.a==e.b?0.:pressure(e.b));if(c<bc){bc=c;best=e;}}return {best};}
 double plan_cost(const P& p){unordered_set<I> ext;for(auto e:p){if(known.count(e.a))ext.insert(e.a);if(known.count(e.b))ext.insert(e.b);}double cost=p.size();for(I v:ext)cost+=pressure(v);return cost;}
 void seed(){if(!known.count(1))add({1,s[0],s[0],'/'}); // materialize dense small seeds; unused nodes pruned
  for(I v=2;v<=min<I>(16,L);v++){if(!known.count(v)){if(has(v))add(leaf(v)[0]);else add({v,v-1,1,'+'});}}
  for(I v=32;v<=min<I>(mode>=3?256:65536,L);v*=2){if(!known.count(v))add({v,v/2,v/2,'+'});}
 }
 int bits(I x){return 64-__builtin_clzll(x);}
 void prepare(){probes=active; bases.clear(); vector<vector<I>> buckets(64); for(auto &kv:dict){I v=kv.first;if(v>1)buckets[bits(v)].push_back(v);} for(auto &b:buckets){sort(b.begin(),b.end()); if(b.size()<=18){probes.insert(probes.end(),b.begin(),b.end());continue;} for(int i=0;i<18;i++)probes.push_back(b[(b.size()-1)*i/17]); if(mode)for(int i=0;i<10;i++)probes.push_back(b[rng()%b.size()]);} sort(probes.begin(),probes.end());probes.erase(unique(probes.begin(),probes.end()),probes.end()); for(I a:probes)if(a>1)bases.push_back(a);all_values=active;for(auto &kv:dict)all_values.push_back(kv.first);sort(all_values.begin(),all_values.end());memo.clear();}
 void append(P& p,const P& q){for(auto e:q){if(known.count(e.v))continue;bool found=false;for(auto z:p)if(z.v==e.v){found=true;break;}if(!found)p.push_back(e);}}
 void push(P& p,E e){if(known.count(e.v))return;for(auto z:p)if(z.v==e.v)return;p.push_back(e);}
 void update(P&best,P p){if(!p.empty()&&(best.empty()||plan_cost(p)<plan_cost(best)))best=move(p);}
 void direct(I v,P& best, bool wide){ // candidate operands may be one-step virtual values
  auto scan=[&](I a){if(a==v)return;auto check=[&](W bb,char op,bool rev){if(bb<1||bb>L||bb==v)return;I b=bb;if(!has(b))return;P p=leaf(a);append(p,leaf(b));push(p,{v,rev?b:a,rev?a:b,op});update(best,move(p));};check((W)v-a,'+',false);check((W)a-v,'-',false);check((W)v+a,'-',true);if(v%a==0)check(v/a,'*',false);check((W)v*a,'/',true);if(a%v==0)check(a/v,'/',false);}; for(I a:probes){scan(a);if(best.size()==1)return;} if(wide&&(best.empty()||best.size()>3)){for(auto &kv:dict){scan(kv.first);if(best.size()<=3)return;}}
 }
 P fallback(I v){if(has(v))return leaf(v);I a=v<256?16:256;if(a>=v)a=2;I q=v/a,r=v%a;P p=fallback(q);append(p,fallback(a));I prod=a*q;if(prod!=q&&prod!=a)push(p,{prod,q,a,'*'});if(r){append(p,fallback(r));push(p,{v,prod,r,'+'});}return p;}
 struct Split{double est;I a,q,r;char op;};
 P solve(I v,int depth){if(has(v))return leaf(v);if(depth==0)return fallback(v);auto it=memo.find(v);if(it!=memo.end())return it->second;P best;direct(v,best,depth==5);if(!best.empty()&&best.size()<=2){memo[v]=best;return best;}
 vector<Split> c; c.reserve(bases.size()*2);
 auto trial=[&](I a,I q,I r,char op){if(q<1||q>=v||a>=v||r==v||(W)a*q>L||(r&&!has(r)))return;I p=a*q;double cost=(known.count(a)?pressure(a):1)+(r?(known.count(r)?pressure(r):1):0)+(has(p)?(known.count(p)?0:1):1)+(r?1:0); if(has(q))cost+=known.count(q)?pressure(q):1; else cost+=max(2.0, (bits(q)-7)*.19); c.push_back({cost,a,q,r,op});};
 for(I a:bases){if(a>=v)break;I q=v/a,r=v%a;trial(a,q,r,'+');if(r)trial(a,q+1,a-r,'-'); // nearby known quotient, nonstandard residues
  if(mode){auto it=lower_bound(probes.begin(),probes.end(),q);for(int k=0;k<2;k++){if(it!=probes.end()){I b=*it;W p=(W)a*b;if(p<=L&&p>0&&p!=v)trial(a,b,(I)(p>v?p-v:v-p),p>v?'-':'+');++it;}}}
 }
 if(depth>=4){for(I a:bases){if(a>=v)break;I q=v/a;auto it=lower_bound(all_values.begin(),all_values.end(),q);int pos=it-all_values.begin();for(int k=max(0,pos-5);k<min((int)all_values.size(),pos+6);k++){I b=all_values[k];W p=(W)a*b;if(p<=L&&p>0&&p!=v)trial(a,b,(I)(p>v?p-v:v-p),p>v?'-':'+');}}}
 if(depth==5){for(auto &kv:dict){I a=kv.first;if(a<=1||a>=v||a>v/2)continue;I q=v/a,r=v%a;trial(a,q,r,'+');if(r)trial(a,q+1,a-r,'-');}}
 sort(c.begin(),c.end(),[](auto a,auto b){return tie(a.est,a.q,a.a,a.r)<tie(b.est,b.q,b.a,b.r);}); int n=0;set<tuple<I,I,I,char>> unique_splits;for(auto x:c){if(!unique_splits.insert({x.a,x.q,x.r,x.op}).second)continue;if(n++>=width)break;if(!best.empty()&&x.est>best.size()+2)break;P p=solve(x.q,depth-1);append(p,leaf(x.a));I prod=x.a*x.q;if(has(prod))append(p,leaf(prod));else push(p,{prod,x.a,x.q,'*'});if(x.r){append(p,leaf(x.r));push(p,{v,prod,x.r,x.op});}update(best,move(p));}
 if(best.empty())best=fallback(v);else {P f=fallback(v);update(best,move(f));}memo[v]=best;return best;
 }
 // t=a*h+r, u=b*h+s: low-cost rational approximation b/a to u/t.
 int paired=0, proposals=0; long long estimated_saved=0;
 struct Hub{double cost;I u,a,b,h,r,s;};
 double price(I x){if(!x)return 0;return known.count(x)?pressure(x):(has(x)?1.:max(2.,(bits(x)-7)*.23));}
 P hub_plan(const Hub& z,I t){
  P p=solve(z.h,4);append(p,solve(z.a,3));append(p,solve(z.b,3));
  auto emit=[&](I target,I a,I r){I prod=(I)((W)a*z.h);if(has(prod))append(p,leaf(prod));else push(p,{prod,a,z.h,'*'});if(r){I rr=abs(r);append(p,solve(rr,3));push(p,{target,prod,rr,r>0?'+':'-'});}};
  emit(t,z.a,z.r);emit(z.u,z.b,z.s);return p;
 }
 bool valid_plan(const P& p,I t,I u){unordered_set<I> have;for(auto e:p){if(!(known.count(e.a)||have.count(e.a))||!(known.count(e.b)||have.count(e.b)))return false;have.insert(e.v);}return (known.count(t)||have.count(t))&&(known.count(u)||have.count(u));}
 P joint(I t,const P& single){
  if(t<256||single.size()<4)return {};vector<Hub> hs;
  vector<I> cs;for(I a:bases)if(a>=2&&a<=65536&&a<t/2&&(known.count(a)||a<=64||a%11==0))cs.push_back(a);
  for(I u:ts){if(u==t||known.count(u)||u<256||(W)u>8*(W)t||(W)t>8*(W)u)continue;
   auto offer=[&](I a,I b){if(a<2||b<2||a>1048576||b>1048576||a>=t||b>=u)return;
    I h0=t/a,h1=u/b,h2=(I)(((W)t+u)/(a+b));
    for(I h:{h0,h0+1,h1,h1+1,h2,h2+1}){if(h<2||h>=min(t,u)||(W)a*h>L||(W)b*h>L)continue;I r=t-a*h,ss=u-b*h;
     if(abs(r)>=t||abs(ss)>=u)continue;
     I cap=1LL<<min(24,max(10,bits(min(t,u))/2));
     if((r&&!has(abs(r))&&abs(r)>cap)||(ss&&!has(abs(ss))&&abs(ss)>cap))continue;
     double c=price(h)+price(a)+price(b)+price(abs(r))+price(abs(ss))+2+(r!=0)+(ss!=0);
     if(c>2*single.size()+2)continue;hs.push_back({c,u,a,b,h,r,ss});
    }
   };
   for(I a:cs){I b0=(I)(((W)u*a+t/2)/t);for(I b: {b0-1,b0,b0+1})if(has(b))offer(a,b);}
   // Continued fraction of u/t; bounded semiconvergents via exact arithmetic.
   I x=u,y=t;W p0=0,p1=1,q0=1,q1=0;
   while(y){I k=x/y; W cap=k;
    if(p1)cap=min(cap,(1048576-p0)/p1);if(q1)cap=min(cap,(1048576-q0)/q1);
    if(cap>=1){for(W j:{(W)1,max((W)1,cap/2),max((W)1,cap-1),cap}){W b=p0+j*p1,a=q0+j*q1;if(a>=2&&b>=2&&a<=1048576&&b<=1048576)offer((I)a,(I)b);}}
    if(cap<k)break;W p=p0+k*p1,q=q0+k*q1;p0=p1;p1=p;q0=q1;q1=q;I r=x%y;x=y;y=r;
   }
  }
  sort(hs.begin(),hs.end(),[](auto x,auto y){return tie(x.cost,x.u,x.h,x.a,x.b)<tie(y.cost,y.u,y.h,y.a,y.b);});
  P best;double gain=0;set<tuple<I,I,I,I>> seen;unordered_map<I,double> solo;
  int n=0;for(auto z:hs){if(!seen.insert({z.u,z.h,z.a,z.b}).second)continue;if(n++>=4)break;++proposals;
   if(!solo.count(z.u)){P q=single;append(q,solve(z.u,4));solo[z.u]=plan_cost(q);}
   P p=hub_plan(z,t);if(!valid_plan(p,t,z.u))continue;double g=solo[z.u]-plan_cost(p);
   if(g>=2.0&&g>gain){gain=g;best=move(p);}
  }
  if(!best.empty()){++paired;estimated_saved+=(long long)gain;}return best;
 }
 void run(){if(mode%2==0)sort(ts.rbegin(),ts.rend());else sort(ts.begin(),ts.end());for(I t:ts){if(known.count(t))continue;prepare();auto p=solve(t,5);auto q=joint(t,p);if(!q.empty())p=move(q);for(auto e:p)add(e);if(!known.count(t))throw runtime_error("target missing");} unordered_set<I> used;P order;function<void(I)> visit=[&](I v){if(root.count(v)||used.count(v))return;auto e=graph.at(v);visit(e.a);visit(e.b);used.insert(v);order.push_back(e);};for(I t:ts)visit(t);cerr<<"joint "<<paired<<" "<<proposals<<" "<<estimated_saved<<"\n";cout<<order.size()<<'\n';for(auto e:order)cout<<e.v<<' '<<e.o<<' '<<e.a<<' '<<e.b<<'\n';}
};
int main(int argc,char**argv){ios::sync_with_stdio(false);cin.tie(nullptr);I L;int ns,nt;if(!(cin>>L>>ns>>nt))return 1;vector<I>s(ns),t(nt);for(I&x:s)cin>>x;for(I&x:t)cin>>x;try{Solver sol(L,s,t,argc>1?atoi(argv[1]):4,argc>2?atoi(argv[2]):1);sol.run();}catch(exception&e){cerr<<e.what()<<'\n';return 2;}}
