#include <bits/stdc++.h>
using namespace std;using I=long long;using W=__int128_t;
struct E{int v,a,b;char o;};struct Raw{I v,a,b;char o;};
struct Solver{
 I L;vector<I> val;unordered_map<I,int> idx;vector<int>S,T;vector<E> es;vector<vector<int>> uses,seeds;int n0;mt19937 rng{1127};
 int id(I v){auto it=idx.find(v);if(it!=idx.end())return it->second;int i=val.size();val.push_back(v);idx[v]=i;return i;}
 int lookup(W v){if(v<1||v>L)return -1;auto it=idx.find((I)v);return it==idx.end()?-1:it->second;}
 map<tuple<int,int,int,char>,int> unique;
 int edge(int v,int a,int b,char o){if(v<0||a<0||b<0||v==a||v==b||find(S.begin(),S.end(),v)!=S.end())return -1;if((o=='+'||o=='*')&&a>b)swap(a,b);auto k=make_tuple(v,a,b,o);auto it=unique.find(k);if(it!=unique.end())return it->second;int j=es.size();unique[k]=j;es.push_back({v,a,b,o});return j;}
 template<class F> void pairs(int a,int b,F f){I x=val[a],y=val[b];f((W)x+y,a,b,'+');f((W)x*y,a,b,'*');if(x>y)f(x-y,a,b,'-');if(y>x)f(y-x,b,a,'-');if(x%y==0)f(x/y,a,b,'/');if(y%x==0)f(y/x,b,a,'/');}
 template<class F> void inverse(int v,int a,F f){I x=val[v],y=val[a];if(x>y)f(x-y,'+',false);if(y>x)f(y-x,'-',false);f((W)x+y,'-',true);if(x%y==0)f(x/y,'*',false);f((W)x*y,'/',true);if(y%x==0)f(y/x,'/',false);}
 void init(vector<vector<Raw>>& gs){for(auto &g:gs)for(auto e:g){id(e.v);id(e.a);id(e.b);}n0=val.size();for(auto &g:gs){vector<int> p(n0,-1);for(auto e:g)p[id(e.v)]=edge(id(e.v),id(e.a),id(e.b),e.o);seeds.push_back(p);} }
 void cross(bool hubs){for(int a=0;a<n0;a++)for(int b=0;b<=a;b++)pairs(a,b,[&](W v,int x,int y,char o){edge(lookup(v),x,y,o);});if(!hubs)return;
 vector<int> freq(n0);for(auto e:es){freq[e.a]++;freq[e.b]++;}vector<int> focus=T;for(int v=0;v<n0;v++)if(freq[v]>=3&&find(T.begin(),T.end(),v)==T.end()&&find(S.begin(),S.end(),v)==S.end())focus.push_back(v);
 struct H{int count=0,last=-1;vector<Raw> make;};unordered_map<I,H> hs;hs.reserve(focus.size()*n0*2);
 for(int v:focus)for(int a=0;a<n0;a++)if(v!=a)inverse(v,a,[&](W h,char o,bool rev){if(h<1||h>L||lookup(h)>=0)return;auto &z=hs[(I)h];if(z.last!=v){z.last=v;z.count++;}});
 for(int a=0;a<n0;a++)for(int b=0;b<=a;b++)pairs(a,b,[&](W h,int x,int y,char o){if(h<1||h>L)return;auto it=hs.find((I)h);if(it!=hs.end()&&it->second.make.size()<4)it->second.make.push_back({(I)h,val[x],val[y],o});});
 vector<pair<int,I>> rank;for(auto &kv:hs)if(!kv.second.make.empty())rank.push_back({kv.second.count,kv.first});sort(rank.begin(),rank.end(),[](auto a,auto b){return a.first!=b.first?a.first>b.first:a.second<b.second;});if(rank.size()>400)rank.resize(400);
 for(auto [count,h]:rank){int v=id(h);for(auto e:hs[h].make)edge(v,idx[e.a],idx[e.b],e.o);}
 for(int v:focus)for(int a=0;a<n0;a++)if(v!=a)inverse(v,a,[&](W h,char o,bool rev){int b=lookup(h);if(b>=n0)edge(v,rev?b:a,rev?a:b,o);});}
 void index(){uses.resize(val.size());for(int i=0;i<(int)es.size();i++){auto e=es[i];uses[e.a].push_back(i);if(e.b!=e.a)uses[e.b].push_back(i);}for(auto &p:seeds)p.resize(val.size(),-1);}
 bool add(int v,vector<int>&p,const vector<int>&src,vector<char>&vis){if(find(S.begin(),S.end(),v)!=S.end()||p[v]>=0)return true;if(vis[v]||src[v]<0)return false;vis[v]=1;auto e=es[src[v]];if(!add(e.a,p,src,vis)||!add(e.b,p,src,vis))return false;vis[v]=0;p[v]=src[v];return true;}
 vector<int> retain(const vector<int>&p,const vector<int>&ts){vector<int> q(val.size(),-1);vector<char>vis(val.size());for(int v:ts)if(!add(v,q,p,vis))throw runtime_error("bad seed");return q;}
 int cost(const vector<int>&p){return count_if(p.begin(),p.end(),[](int x){return x>=0;});}
 vector<int> rebuild(vector<int> p,vector<int> todo,int mode){int N=val.size(),M=es.size();vector<int> rank(N);for(int &x:rank)x=rng()%1000;while(!todo.empty()){
 vector<double>d(N,1e30),acc(M);vector<int>src(N,-1),pending(M);vector<char>done(N);using Q=pair<double,int>;priority_queue<Q,vector<Q>,greater<Q>> pq;for(int i=0;i<M;i++)pending[i]=1+(es[i].a!=es[i].b);for(int v:S){d[v]=0;pq.push({0,v});}for(int v=0;v<N;v++)if(p[v]>=0){d[v]=0;pq.push({0,v});}
 while(!pq.empty()){auto [dist,v]=pq.top();pq.pop();if(done[v])continue;done[v]=1;for(int k:uses[v]){auto e=es[k];acc[k]+=dist;if(--pending[k])continue;double nd=acc[k]+1.0+(mode%3==1?rank[e.v]*.0003:mode%3==2?rank[e.v]*.0008:0);if(nd<d[e.v]){d[e.v]=nd;src[e.v]=k;pq.push({nd,e.v});}}}
 int j=0;if(mode%4!=3)for(int i=1;i<(int)todo.size();i++){int v=todo[i],u=todo[j];double a=d[v]+(mode%4==2?.001*rank[v]:0),b=d[u]+(mode%4==2?.001*rank[u]:0);if(a<b)j=i;}int v=todo[j];todo.erase(todo.begin()+j);vector<char>vis(N);if(!add(v,p,src,vis))throw runtime_error("unreachable");}return retain(p,T);}
 vector<int> solve(int rounds){vector<int>best;int bc=INT_MAX;for(auto p:seeds){p=retain(p,T);if(cost(p)<bc){bc=cost(p);best=p;}}vector<int>cur=best;for(int k=0;k<rounds;k++){auto targets=T;shuffle(targets.begin(),targets.end(),rng);int keep=k%7==0?0:targets.size()*(25+int(rng()%65))/100;vector<int>fixed(targets.begin(),targets.begin()+keep),todo(targets.begin()+keep,targets.end());auto p=rebuild(retain(cur,fixed),todo,k);int c=cost(p);if(c<bc){bc=c;best=p;}if(c<=cost(cur)||k%9==0)cur=p;if(k%11==0)cur=best;}return best;}
 void output(const vector<int>&p){cout<<cost(p)<<'\n';vector<char>done(val.size());for(int v:S)done[v]=1;function<void(int)>dfs=[&](int v){if(done[v])return;auto e=es[p[v]];dfs(e.a);dfs(e.b);done[v]=1;cout<<val[v]<<' '<<e.o<<' '<<val[e.a]<<' '<<val[e.b]<<'\n';};for(int t:T)dfs(t);}
};
int main(int argc,char**argv){ios::sync_with_stdio(false);cin.tie(nullptr);try{Solver s;int ns,nt,ng;cin>>s.L>>ns>>nt>>ng;I x;for(int i=0;i<ns;i++){cin>>x;s.S.push_back(s.id(x));}for(int i=0;i<nt;i++){cin>>x;s.T.push_back(s.id(x));}vector<vector<Raw>>gs(ng);for(auto &g:gs){int n;cin>>n;g.resize(n);for(auto &e:g)cin>>e.v>>e.o>>e.a>>e.b;}s.init(gs);s.cross(argc>1&&atoi(argv[1]));s.index();auto p=s.solve(argc>2?atoi(argv[2]):24);s.output(p);cerr<<s.n0<<' '<<s.val.size()<<' '<<s.es.size()<<'\n';}catch(exception&e){cerr<<e.what()<<'\n';return 2;}}
