import os,json,hmac,sqlite3,time,re,threading,html,urllib.request,urllib.error,urllib.parse
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
os.chdir(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists('.env'):
    for l in open('.env'):
        if '=' in l and not l.lstrip().startswith('#'):
            k,v=l.strip().split('=',1);os.environ.setdefault(k.strip(),v.strip())
E=os.environ.get

# --- SUPABASE AUTH VERIFICATION ADDED ---
SUP_URL=E('SUPABASE_URL','').rstrip('/');SUP_ANON=E('SUPABASE_ANON_KEY','')
_ucache={}
def verify(req):
    tok=(req.headers.get('Authorization') or '').replace('Bearer ','').strip()
    if not tok or not SUP_URL:return None
    now=time.time()
    if tok in _ucache and _ucache[tok][1]>now:return _ucache[tok][0]
    try:
        r=urllib.request.Request(SUP_URL+'/auth/v1/user',headers={'apikey':SUP_ANON,'Authorization':'Bearer '+tok,'User-Agent':'fitstreak/4'})
        u=json.load(urllib.request.urlopen(r,timeout=10))
        uid=u['id'];_ucache[tok]=(uid,now+300);return uid
    except Exception as e:
        print('auth fail',e);return None
# ----------------------------------------

GROQ,TAV,ADMIN=E('GROQ_API_KEY',''),E('TAVILY_API_KEY',''),E('ADMIN_KEY','')
FREE,PRO,PRICE=int(E('FREE_PER_DAY','10')),int(E('PRO_PER_DAY','150')),int(E('PRICE_INR','199'))
UPI,UPN,SUP=E('UPI_ID',''),E('UPI_NAME',''),E('SUPPORT_CONTACT','')
VISION=E('GROQ_VISION_MODEL','qwen/qwen3.6-27b');G='https://api.groq.com/openai/v1'
D=sqlite3.connect('fitstreak.db',check_same_thread=False);L=threading.Lock()
D.executescript('pragma journal_mode=wal;create table if not exists u(id text primary key,sub int default 0);create table if not exists n(id text,d text,c int,primary key(id,d));create table if not exists pay(utr text primary key,uid text,payer text,st text,ts int)')
def q(sql,a=()):
    with L:
        try:r=D.execute(sql,a).fetchall();D.commit();return r
        except Exception:D.rollback();raise
td=lambda:time.strftime('%Y-%m-%d')
def active(u):
    r=q('select sub from u where id=?',(u,));return bool(r and r[0][0])
def left(u):
    r=q('select c from n where id=? and d=?',(u,td()));return max(0,(PRO if active(u) else FREE)-(r[0][0] if r else 0))
def use(u,d=1):q('insert into n values(?,?,?) on conflict(id,d) do update set c=max(0,c+?)',(u,td(),max(d,0),d))
RL={}
def rl(k,n,sec):
    now=time.time();a=[t for t in RL.get(k,[]) if now-t<sec]
    if len(a)>=n:RL[k]=a;return False
    a.append(now);RL[k]=a;return True
SYS='''You are FitStreak, a precise, friendly, voice-first health coach that also runs the user's tracking app. Reply ONLY with JSON text (do not use native tool calling): {"say":"...","actions":[...],"search":null,"followups":["...","..."]}
"say": what the user hears and reads. 1 to 4 short sentences. Plain text, no emojis, no markdown, no symbols. Use the user's language; if they use Hindi or Hinglish, reply in Hinglish in Roman script. ALWAYS provide a helpful, direct answer. NEVER reply with just "Done.", "Ok.", or "Sure." unless an action was successfully performed.
"search": a short web search query ONLY when the answer needs current or checkable facts you are not sure about (news, prices, research claims, nutrition facts of a specific branded food). Otherwise null. When search is set, leave "say" empty.
"followups": 2 or 3 short statements or questions the USER would say to YOU next (CRITICAL: NEVER ask the user a question here. Say "Tell me about discounts" instead of "Do you want discounts?"), in the user's language.
"actions": use only when the user asks to record, change or open something:
{"type":"log_set","exercise":"Bench Press","weight":30,"reps":10,"sets":3} (kg, 0 for bodyweight)
{"type":"log_meal","name":"2 rotis and paneer sabji","calories":520,"protein":22,"carbs":60,"fat":20} (estimate for a typical portion and say it is approximate)
{"type":"water","n":1} (glasses, negative removes)
{"type":"sleep","hours":7}
{"type":"day_type","name":"Push"}
{"type":"undo"} (last set) / {"type":"undo_meal"}
{"type":"goto","tab":"home|meals|progress|coach|profile"}
{"type":"new_chat"} / {"type":"scan"} (open the food scanner) / {"type":"upgrade"} (open the Pro payment screen)
{"type":"theme","mode":"dark|light"} / {"type":"set_name","name":"Ravi"} / {"type":"set_goal","calories":2200}
Never invent sets, weights or reps; if missing, ask in "say" and add no action. Answer progress questions from the user data. Help only with fitness, nutrition, wellness and this app.
Safety: you are not a doctor. Never diagnose, advise medication, supplement doses, steroids, crash diets or training through pain. For pain, injury or medical issues advise a doctor. If the user seems distressed, respond with care and urge emergency help.'''
SYS2='''Answer the user's question using ONLY the numbered sources. Cite claims like [1] or [2]. If the sources do not answer it, say so plainly. Reply ONLY with JSON text (do not use native tool calling): {"say":"...","followups":["...","..."]}. "say": 2 to 5 short sentences, plain text, no markdown, same language as the question. You MUST provide a detailed answer using the sources. For prices, always add a short note that prices may vary and to check the seller's site. Use inline citations like [1] or [2] in your text. NEVER reply with generic responses. Write at least 2 sentences. "followups": 2 or 3 short statements or questions the USER would say to YOU next (CRITICAL: NEVER ask the user a question here. Say "Show me specific brand price" instead of "Do you want a specific brand price?"), in the user's language. You are not a doctor: no diagnosis, medication or supplement doses, steroids, crash diets; advise a doctor for medical issues.'''
OK={'log_set','log_meal','water','sleep','day_type','undo','undo_meal','goto','new_chat','scan','upgrade','theme','set_name','set_goal'}
RISK=[(r'suicid|kill myself|end my life|self.?harm|hurt myself|jeena nahi|marna chahta','I am really sorry you feel this way. You are not alone. Please call 112 if you are in danger, or Tele-MANAS 14416 (free, 24x7) in India, and stay with someone you trust.'),
(r"chest pain|can.?t breathe|shortness of breath|fainted|passed out|heart attack|seizure",'Please stop exercising and rest now. These symptoms can be serious. See a doctor, or call 112 if severe or sudden.'),
(r'steroid|sarm|clenbuterol|trenbolone|\bhgh\b|\bdnp\b|anavar|dianabol','I cannot advise on steroids or performance drugs. They are risky and need a doctor. I can help with training, protein, sleep and recovery.'),
(r'anorexi|bulimi|purge|starv|laxative|under 1000 cal|khana chhod','I cannot help with extreme dieting or purging. Please talk to a doctor or dietitian. I can help with steady training and regular meals.')]
def jparse(s):
    s = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', s or '', flags=re.S)
    try:
        j = json.loads(s)
        return j.get('arguments', j) if isinstance(j, dict) and 'name' in j else j
    except Exception:
        m = re.search(r'\{.*\}',s or '',re.S)
        if m:
            try:
                j = json.loads(m.group(0))
                return j.get('arguments', j) if isinstance(j, dict) and 'name' in j else j
            except: pass
        return {}
PICK=['']
def pick():
    
    if not PICK[0]:
        try:
            r=urllib.request.Request(G+'/models',headers={'Authorization':'Bearer '+GROQ,'User-Agent':'fitstreak/4'})
            ids=[x['id'] for x in json.load(urllib.request.urlopen(r,timeout=15))['data']]
        except Exception as ex:
            print('models error',ex);ids=[]
        ok=[i for i in ids if not re.search('whisper|guard|tts|orpheus|compound|embed|safeguard',i)]
        PICK[0]=next((p for p in('openai/gpt-oss-20b','llama-3.1-8b-instant') if p in ids),ok[0] if ok else 'openai/gpt-oss-20b')
        print('Groq model:',PICK[0])
    return PICK[0]
def groq(msgs,model=None,js=True,mt=1500):
    for _ in(0,1):
        m=model or pick();body={'model':m,'messages':msgs,'temperature':.3,'max_completion_tokens':mt}
        if js:body['response_format']={'type':'json_object'}
        if 'gpt-oss' in m:body['reasoning_effort']='low'
        try:
            req=urllib.request.Request(G+'/chat/completions',json.dumps(body).encode(),{'Authorization':'Bearer '+GROQ,'Content-Type':'application/json','User-Agent':'fitstreak/4'})
            return json.load(urllib.request.urlopen(req,timeout=60))['choices'][0]['message']['content'] or ''
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print('groq',e.code,err_body[:300])
            if e.code == 400 and 'tool_use_failed' in err_body:
                try:
                    err_json = json.loads(err_body)
                    failed_gen = err_json['error'].get('failed_generation', '')
                    
                    # Smart Fix: If model tries to use web.run, convert it to our expected JSON
                    if 'web.run' in failed_gen:
                        m_q = re.search(r'"query"\s*:\s*"([^"]+)"', failed_gen)
                        if m_q:
                            q_str = m_q.group(1)
                            print('Model requested web search:', q_str)
                            return json.dumps({"say": "", "actions": [], "search": q_str, "followups": []})
                            
                    # General Recovery for other tool calls
                    m = re.search(r'"arguments"\s*:\s*(\{.*)', failed_gen, re.S)
                    if m:
                        args_str = m.group(1)
                        if not args_str.endswith('}'): args_str += '}'
                        return args_str
                except Exception as ex:
                    print('recovery failed', ex)
            if model:break
            PICK[0]=''
    raise RuntimeError('groq failed')
def web(s):
    if not TAV:return []
    try:
        req=urllib.request.Request('https://api.tavily.com/search',json.dumps({'query':s[:200],'max_results':5,'search_depth':'basic'}).encode(),{'Authorization':'Bearer '+TAV,'Content-Type':'application/json'})
        return [{'title':str(x.get('title',''))[:120],'url':str(x.get('url','')),'text':str(x.get('content',''))[:700]} for x in json.load(urllib.request.urlopen(req,timeout=20)).get('results',[])][:5]
    except Exception as e:
        print('search error',e);return []
def clean_fu(l):return [str(x)[:90] for x in (l if isinstance(l,list) else [])][:3]
def ask(b):
    u=str(b.get('uid',''))[:64];t=str(b.get('text',''))[:500].strip()
    if not u or not t:return 400,{'error':'bad request'}
    for p,m in RISK:
        if re.search(p,t,re.I):return 200,{'say':m,'actions':[],'followups':[],'sources':[]}
    if not GROQ:return 500,{'error':'GROQ_API_KEY missing'}
    if left(u)<=0:return 402,{'error':'limit'}
    use(u)
    h=[{'role':'user' if m.get('r')=='u' else 'assistant','content':str(m.get('t',''))[:300]} for m in (b.get('hist') or [])[-6:] if isinstance(m,dict)]
    msgs=[{'role':'system','content':SYS+'\nToday: '+time.strftime('%A %d %B %Y')+'\nUser data: '+json.dumps(b.get('ctx',{}),ensure_ascii=False)[:3000]}]+h+[{'role':'user','content':t}]
    try:
        j=jparse(groq(msgs));acts=[a for a in j.get('actions',[]) if isinstance(a,dict) and a.get('type') in OK][:6]
        say,fu,src=str(j.get('say',''))[:600],clean_fu(j.get('followups')),[]
        sq=j.get('search')
        if isinstance(sq,str) and sq.strip():
            res=web(sq)
            if not res:
                # Agar Tavily fail ho jaye
                say = "I couldn't find live results for that right now. Please try again."
                return 200,{'say':say,'actions':[],'followups':[],'sources':[]}
                
            blk='\n'.join('[%d] %s\n%s'%(i+1,r['title'],r['text']) for i,r in enumerate(res))
            # Use llama-3.1-8b-instant for search summarization (much more reliable)
            j2=jparse(groq([{'role':'system','content':SYS2},{'role':'user','content':'Question: '+t+'\nSources:\n'+blk}], model=pick()))
            say2 = str(j2.get('say','')).strip()
            
            # Strict check for bad responses
            if say2 and say2.lower().rstrip('.') not in ('done', 'ok', 'okay', 'sure', ''):
                say = say2[:900]
            else:
                # Ultimate Fallback: If AI fails, give a direct summary of the first result
                say = f"According to {res[0]['title']}, {res[0]['text'][:250]}..."
            
            fu=clean_fu(j2.get('followups')) or fu
            src=[{'n':i+1,'title':r['title'],'url':r['url']} for i,r in enumerate(res)]
        return 200,{'say':say,'actions':acts,'followups':fu,'sources':src}
    except Exception as e:
        print('ask error',e);use(u,-1);return 502,{'error':'ai unavailable'}
def num(v,m):
    try:return max(0,min(m,round(float(v))))
    except Exception:return 0
def scan(b):
    u=str(b.get('uid',''))[:64];img=str(b.get('image',''))
    if not u or not img.startswith('data:image/') or len(img)>2500000:return 400,{'error':'bad image'}
    if not GROQ:return 500,{'error':'GROQ_API_KEY missing'}
    if left(u)<=0:return 402,{'error':'limit'}
    use(u)
    try:
        j=jparse(groq([{'role':'user','content':[{'type':'text','text':'Identify the food in this photo and estimate one typical serving. Reply ONLY with JSON text (do not use native tool calling): {"food":"name","calories":0,"protein":0,"carbs":0,"fat":0,"note":"short portion note"}. If no food is visible reply {"food":""}.'},{'type':'image_url','image_url':{'url':img}}]}],model=VISION,js=False,mt=2500))
    except Exception as e:
        print('scan error',e);use(u,-1);return 502,{'error':'scan unavailable'}
    f=str(j.get('food',''))[:60]
    return 200,{'food':f,'calories':num(j.get('calories'),3000),'protein':num(j.get('protein'),300),'carbs':num(j.get('carbs'),500),'fat':num(j.get('fat'),300),'note':str(j.get('note',''))[:100]} if f else {'food':''}
def status(u):
    p=q('select st from pay where uid=? order by ts desc limit 1',(u,));s=p[0][0] if p else ''
    a=active(u)
    try: current_model = pick()
    except: current_model = 'unknown'
    return {'active':a,'left':left(u),'price':PRICE,'pending':s=='pending' and not a,'rejected':s=='rejected' and not a,'upi':UPI,'upn':UPN,'support':SUP,'search':bool(TAV),'model':current_model}
def pay(b,ip):
    u=str(b.get('uid',''))[:64];utr=re.sub(r'\D','',str(b.get('utr','')));payer=str(b.get('payer','')).strip()[:60]
    if not u or len(utr)!=12 or not payer:return 400,{'error':'Enter the 12 digit UTR and the payer name'}
    if active(u):return 200,{'ok':1}
    if not rl(ip+'pay',8,3600) or q('select count(*) from pay where uid=? and ts>?',(u,time.time()-86400))[0][0]>=3:return 429,{'error':'Too many attempts. Please try later.'}
    try:q('insert into pay values(?,?,?,?,?)',(utr,u,payer,'pending',int(time.time())))
    except sqlite3.IntegrityError:return 409,{'error':'This UTR was already submitted'}
    return 200,{'ok':1}
def recover(b,ip):
    u=str(b.get('uid',''))[:64];utr=re.sub(r'\D','',str(b.get('utr','')))
    if not u or len(utr)!=12 or not rl(ip+'rec',6,3600):return 400,{'error':'Check the UTR and try later'}
    r=q("select uid from pay where utr=? and st='approved'",(utr,))
    if not r:return 404,{'error':'No approved payment found for this UTR'}
    q('update pay set uid=? where utr=?',(u,utr));q('update u set sub=0 where id=?',(r[0][0],));q('insert into u values(?,1) on conflict(id) do update set sub=1',(u,))
    return 200,{'ok':1}
def okey(k):return bool(ADMIN) and hmac.compare_digest(str(k),ADMIN)
def admin_page(key):
    h=lambda s:html.escape(str(s));f=lambda t:time.strftime('%d %b %H:%M',time.localtime(t))
    o='<meta name=viewport content="width=device-width,initial-scale=1"><body style="font-family:sans-serif;max-width:520px;margin:auto;padding:16px"><h2>Pending payments (Rs %d)</h2><p>Open your UPI app and confirm the credit with this UTR before approving.</p>'%PRICE
    for utr,uid,payer,ts in q("select utr,uid,payer,ts from pay where st='pending' order by ts"):
        o+='<div style="border:1px solid #ccc;padding:12px;margin:10px 0;border-radius:10px"><b>UTR %s</b><br>Payer: %s<br>Ref: %s · %s<form method=post action=/admin/act style="margin-top:8px"><input type=hidden name=key value="%s"><input type=hidden name=utr value="%s"><button name=act value=approve>Approve</button> <button name=act value=reject>Reject</button></form></div>'%(h(utr),h(payer),h(uid[:6].upper()),f(ts),h(key),h(utr))
    o+='<h3>Recent</h3>'+''.join('<p>%s · %s · %s</p>'%(h(a),h(b),h(c)) for a,b,c in [(r[0],r[1],r[2]) for r in q("select utr,payer,st from pay where st!='pending' order by ts desc limit 15")])
    return o.encode()
def act(utr,a):
    r=q("select uid from pay where utr=? and st='pending'",(utr,))
    if not r:return
    q('update pay set st=? where utr=?',('approved' if a=='approve' else 'rejected',utr))
    if a=='approve':q('insert into u values(?,1) on conflict(id) do update set sub=1',(r[0][0],))
class H(SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*');self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type');self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');self.send_header('Access-Control-Allow-Origin', '*');self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type');self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');self.send_header('Cache-Control','no-cache');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');super().end_headers()
    def send(self,c,body,ct='application/json',loc=None):
        try:
            self.send_response(c);self.send_header('Content-Type',ct);self.send_header('Content-Length',str(len(body)))
            if loc:self.send_header('Location',loc)
            self.end_headers();self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
    def js(self,c,o):self.send(c,json.dumps(o).encode())
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    def ip(self):return self.headers.get('X-Forwarded-For','').split(',')[0].strip() or self.client_address[0]
    def do_GET(self):
        p,_,qs=self.path.partition('?');a=urllib.parse.parse_qs(qs)
        # --- CHANGED: STATUS LOCK ---
        if p=='/api/status':
            uid=verify(self)
            if not uid:return self.js(401,{'error':'login required'})
            return self.js(200,status(uid))
        # ----------------------------
        if p=='/api/health':return self.js(200,{'ok':1,'groq':bool(GROQ),'search':bool(TAV)})
        if p=='/admin':
            k=a.get('key',[''])[0]
            return self.send(200,admin_page(k),'text/html; charset=utf-8') if okey(k) else self.send(403,b'Forbidden','text/plain')
        if p.startswith('/api') or p.startswith('/admin') or p.lstrip('/').startswith(('server.py','fitstreak.db','.')):return self.js(404,{})
        super().do_GET()
    def do_POST(self):
        n=int(self.headers.get('Content-Length',0) or 0);p=self.path
        if n>(3000000 if p=='/api/scan' else 20000):return self.js(413,{})
        raw=self.rfile.read(n)
        if p=='/admin/act':
            f={k:v[0] for k,v in urllib.parse.parse_qs(raw.decode('utf-8','ignore')).items()}
            if not okey(f.get('key','')) or f.get('act') not in('approve','reject'):return self.send(403,b'Forbidden','text/plain')
            act(re.sub(r'\D','',f.get('utr','')),f['act']);return self.send(303,b'','text/plain','/admin?key='+urllib.parse.quote(f['key']))
        try:b=json.loads(raw or b'{}')
        except Exception:return self.js(400,{})
        
        # --- CHANGED: ROUTES LOCK ---
        if p in ('/api/chat','/api/scan','/api/pay','/api/recover','/api/migrate'):
            uid=verify(self)
            if not uid:return self.js(401,{'error':'login required'})
            if p=='/api/migrate':
                old=str(b.get('old',''))[:64]
                if old and old!=uid:
                    q('insert or ignore into n(id,d,c) select ?,d,c from n where id=?',(uid,old))
                    q('insert or ignore into u(id,sub) select ?,sub from u where id=?',(uid,old))
                    q('delete from n where id=?',(old,))
                    q('delete from u where id=?',(old,))
                return self.js(200,{'ok':1})
            b['uid']=uid
            if p=='/api/chat' and not rl(self.ip()+'chat',30,3600):
                return self.js(429,{'error':'slow down'})
        # --------------------------
        
        if p=='/api/chat':c,o=ask(b)
        elif p=='/api/scan':c,o=scan(b)
        elif p=='/api/pay':c,o=pay(b,self.ip())
        elif p=='/api/recover':c,o=recover(b,self.ip())
        else:c,o=404,{}
        self.js(c,o)
if __name__=='__main__':
    print('FitStreak: http://localhost:'+E('PORT','8080'),'| Groq:','set' if GROQ else 'MISSING','| Web search:','on' if TAV else 'off','| Admin:','on' if ADMIN else 'OFF (set ADMIN_KEY)','| UPI:',UPI or 'MISSING')
    ThreadingHTTPServer((E('HOST','0.0.0.0'),int(E('PORT','8080'))),H).serve_forever()
