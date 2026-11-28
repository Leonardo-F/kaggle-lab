#include <bits/stdc++.h>
using namespace std;using I=long long;using W=__int128_t;
struct E{I v,a,b;char op;};using G=map<I,E>;
struct Solver{
 I L;set<I>S,T;G g;int mode,moves=0,novel=0,tests=0,four=0,chain=0;
 vector<I> topo(){vector<I>r;set<I>seen=S;function<void(I)>f=[&](I v){if(seen.count(v))return;auto e=g.at(v);f(e.a);f(e.b);seen.insert(v);r.push_back(v);};for(I t:T)f(t);return r;}
 void prune(){auto r=topo();G out;for(I v:r)out[v]=g.at(v);g.swap(out);}
 template<class F>void inverse(I t,I a,F f){auto send=[&](W b,char o,bool rev){if(b>=1&&b<=L)f((I)b,o,rev);};send((W)t-a,'+',0);send((W)a-t,'-',0);send((W)t+a,'-',1);if(t%a==0)send(t/a,'*',0);if(a%t==0)send(a/t,'/',0);send((W)t*a,'/',1);}
 bool rewrite(I v){
  map<I,int>refs;map<I,vector<I>>users;for(auto [x,e]:g){for(I a:set<I>{e.a,e.b}){refs[a]++;users[a].push_back(x);}}for(I t:T)refs[t]++;
  set<I>removed{v};vector<I>q{v};for(size_t i=0;i<q.size();i++){auto e=g.at(q[i]);for(I a:set<I>{e.a,e.b})if(g.count(a)&&!--refs[a]){removed.insert(a);q.push_back(a);}}
  if(removed.size()<2)return false;
  set<I>forbidden{v};vector<I>u{v};for(size_t i=0;i<u.size();i++)for(I x:users[u[i]])if(forbidden.insert(x).second)u.push_back(x);
  set<I>available=S;for(auto [x,e]:g)if(!removed.count(x)&&!forbidden.count(x))available.insert(x);
  vector<I>A(available.begin(),available.end());vector<E>best;
  auto improve=[&](vector<E>p){if(p.size()<removed.size()&&(best.empty()||p.size()<best.size()))best=move(p);};
  for(I a:A){inverse(v,a,[&](I b,char op,bool rev){if(available.count(b))improve({{v,rev?b:a,rev?a:b,op}});});if(!best.empty())break;}
  if(best.empty()&&removed.size()>=3){
   unordered_map<I,E>D;D.reserve(A.size()*A.size()*2);auto put=[&](W x,I a,I b,char o){if(x<1||x>L||available.count((I)x)||forbidden.count((I)x))return;D.try_emplace((I)x,E{(I)x,a,b,o});};
   for(size_t i=0;i<A.size();i++){I a=A[i];for(size_t j=0;j<=i;j++){I b=A[j];put((W)a+b,a,b,'+');put((W)a*b,a,b,'*');if(a>b)put(a-b,a,b,'-');if(a%b==0)put(a/b,a,b,'/');}}
   for(I a:A){inverse(v,a,[&](I b,char op,bool rev){auto it=D.find(b);if(it!=D.end())improve({it->second,{v,rev?b:a,rev?a:b,op}});});if(!best.empty())break;}
   if(best.empty()&&mode>=3&&removed.size()>=4){for(auto [a,e]:D){inverse(v,a,[&](I b,char op,bool rev){auto it=D.find(b);if(it==D.end())return;vector<E>p{e};if(a!=b)p.push_back(it->second);p.push_back({v,rev?b:a,rev?a:b,op});improve(move(p));});if(!best.empty())break;}}
   // Bounded inverse meet-in-the-middle, with exact integer checks.
   if(best.empty()&&mode>=4&&removed.size()>=4){
    long long budget=80000;
    for(I a:A){if(!best.empty()||budget<=0)break;inverse(v,a,[&](I m,char o,bool rev){
      if(!best.empty()||available.count(m)||forbidden.count(m))return;
      for(I b:A){if(!best.empty()||--budget<=0)break;inverse(m,b,[&](I x,char p,bool r){auto it=D.find(x);if(it==D.end()||x==m)return;improve({it->second,{m,r?x:b,r?b:x,p},{v,rev?m:a,rev?a:m,o}});});}
    });}
    if(!best.empty())chain++;
   }
   if(best.empty()&&mode>=4&&removed.size()>=5){
    vector<I> keys;keys.reserve(D.size());for(auto &kv:D)keys.push_back(kv.first);sort(keys.begin(),keys.end());
    // Deterministic spread through the one-op dictionary, not only small values.
    long long budget=120000;size_t stride=max<size_t>(1,keys.size()/192);
    for(I a:A){if(!best.empty()||budget<=0)break;inverse(v,a,[&](I m,char o,bool rev){
      if(!best.empty()||available.count(m)||forbidden.count(m))return;
      for(size_t j=0;j<keys.size();j+=stride){if(!best.empty()||--budget<=0)break;I x=keys[j];if(x==m)continue;inverse(m,x,[&](I y,char p,bool r){auto it=D.find(y);if(it==D.end()||y==m)return;vector<E> es{D.at(x)};if(x!=y)es.push_back(it->second);es.push_back({m,r?y:x,r?x:y,p});es.push_back({v,rev?m:a,rev?a:m,o});improve(move(es));});}
    });}
    if(!best.empty())four++;
   }

  }
  tests++;if(best.empty())return false;for(auto e:best)if(e.v!=v&&!g.count(e.v)&&!S.count(e.v))novel++;
  for(I x:removed)g.erase(x);for(auto e:best)g[e.v]=e;prune();moves++;return true;
 }
 void run(){prune();for(int pass=0;pass<2;pass++){int old=moves;auto r=topo();reverse(r.begin(),r.end());for(I v:r)if(g.count(v))rewrite(v);if(old==moves)break;}auto r=topo();cout<<r.size()<<'\n';for(I v:r){auto e=g.at(v);cout<<v<<' '<<e.op<<' '<<e.a<<' '<<e.b<<'\n';}cerr<<"moves="<<moves<<" novel="<<novel<<" chain="<<chain<<" four="<<four<<" tests="<<tests<<'\n';}
};
int main(int argc,char**argv){Solver s;s.mode=argc>1?atoi(argv[1]):3;int ns,nt,n;cin>>s.L>>ns>>nt>>n;I x;for(int i=0;i<ns;i++){cin>>x;s.S.insert(x);}for(int i=0;i<nt;i++){cin>>x;s.T.insert(x);}for(int i=0;i<n;i++){E e;cin>>e.v>>e.op>>e.a>>e.b;s.g[e.v]=e;}s.run();}
