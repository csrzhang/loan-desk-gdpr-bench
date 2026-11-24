"""Local Loan Desk WSGI service. Run python app.py to start."""
import argparse
import json
import os
import re
import secrets
import time
from http import HTTPStatus
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from wsgiref.simple_server import make_server

import store
import views
from store import Problem, require

ROOT=Path(__file__).resolve().parent

class Application:
    def __init__(self, path, passwords):
        self.path=path
        self.passwords=passwords
        self.sessions={}
        store.setup(path)

    def __call__(self, env, start_response):
        method=env["REQUEST_METHOD"]
        path=env["PATH_INFO"]
        headers=[("Cache-Control","no-store"),("X-Content-Type-Options","nosniff"),
                 ("Content-Security-Policy","default-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")]
        status=200
        mime="text/html; charset=utf-8"
        try:
            require(method in ("GET","POST"),"Method unavailable.",405)
            require(re.fullmatch(r"(localhost|127\.0\.0\.1)(:\d+)?", env.get("HTTP_HOST","")),"Use a loopback address.",403)
            if method=="POST" and env.get("HTTP_ORIGIN"):
                require(env["HTTP_ORIGIN"]=="http://"+env["HTTP_HOST"],"Invalid origin.",403)
            cookie=SimpleCookie()
            try:
                cookie.load(env.get("HTTP_COOKIE",""))
            except CookieError:
                pass
            sid=cookie["session"].value if "session" in cookie else ""
            now=time.monotonic()
            self.sessions={k:v for k,v in self.sessions.items() if v[2]>now}
            who,token,_=self.sessions.get(sid,("","",0))
            data={}
            if method=="POST":
                require(env.get("CONTENT_TYPE","").split(";")[0]=="application/x-www-form-urlencoded","Expected form fields.",415)
                size=int(env.get("CONTENT_LENGTH") or 0)
                require(0<=size<=16000,"Form too large.",413)
                parsed=parse_qs(env["wsgi.input"].read(size).decode(),keep_blank_values=True,max_num_fields=18)
                require(all(len(v)==1 for v in parsed.values()),"Duplicate form field.")
                data={k:v[0] for k,v in parsed.items()}
            location=None
            if path=="/style.css" and method=="GET":
                body=(ROOT/"style.css").read_text()
                mime="text/css; charset=utf-8"
            elif path=="/login" and method=="POST":
                user=data.get("user","")
                require(user in self.passwords and secrets.compare_digest(data.get("password","").encode(),self.passwords[user].encode()),"Invalid account or password.",403)
                self.sessions.pop(sid,None)
                sid=secrets.token_urlsafe(32)
                self.sessions[sid]=(user,secrets.token_urlsafe(24),now+8*3600)
                headers.append(("Set-Cookie",f"session={sid}; Path=/; HttpOnly; SameSite=Strict"))
                location="/"
            elif not who:
                require(path=="/" and method=="GET","Sign in to continue.",401)
                body=views.login()
            else:
                if method=="POST":
                    require(secrets.compare_digest(data.pop("csrf","").encode(),token.encode()),"Invalid form token.",403)
                with store.database(self.path) as db:
                    db.execute("BEGIN IMMEDIATE" if method=="POST" else "BEGIN")
                    if path=="/" and method=="GET":
                        cases=store.rows(db,"SELECT c.id,c.stage,s.title FROM cases c JOIN summaries s ON s.cid=c.id WHERE c.owner=? OR c.officer=? ORDER BY c.id DESC",(who,who))
                        body=views.dashboard(db,who,token,cases)
                    elif path=="/logout" and method=="POST":
                        self.sessions.pop(sid,None)
                        headers.append(("Set-Cookie","session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"))
                        location="/"
                    elif path=="/apply" and method=="POST":
                        location="/case/"+str(store.submit(db,who,data))
                    elif path=="/preference" and method=="POST":
                        store.preference(db,who,data.get("purpose"),data.get("value"))
                        location="/"
                    elif path=="/campaign" and method=="POST":
                        store.campaign(db,who)
                        location="/"
                    else:
                        route=re.fullmatch(r"/case/(\d{1,18})(?:/([a-z-]+))?",path)
                        require(route,"Page unavailable.",404)
                        cid=int(route[1])
                        c=store.get_case(db,who,cid)
                        op=route[2]
                        if method=="POST" and op:
                            store.action(db,who,cid,op,data)
                            location="/" if op=="erase" else f"/case/{cid}"
                        elif method=="GET" and op in ("access","portable","offer"):
                            if op=="offer":
                                require(c["stage"] in ("accepted","offered") and not c["restricted"],"Offer unavailable.",409)
                                item=store.offer(db,c)
                            else:
                                require(who==c["owner"],"Borrower required.",403)
                                item=store.access(db,c) if op=="access" else store.portable(c)
                            mime="application/json"
                            headers.append(("Content-Disposition",f'attachment; filename="loan-{cid}-{op}.json"'))
                            body=json.dumps(item,indent=2)
                        elif method=="GET" and op is None:
                            a=store.access(db,c)
                            body=views.detail(c,token,who,a["timeline"],a["jobs"])
                        else:
                            raise Problem("Page unavailable.",404)
            if location:
                status=303
                headers.append(("Location",location))
                body=""
        except (Problem, ValueError) as exc:
            status=exc.status if isinstance(exc,Problem) else 400
            msg=str(exc) if isinstance(exc,Problem) else "Invalid form."
            body=views.page("Request unavailable","<section><h2>"+views.h(msg)+'</h2><a href="/">Return to workspace</a></section>')
        out=body.encode()
        start_response(f"{status} {HTTPStatus(status).phrase}",headers+[("Content-Type",mime),("Content-Length",str(len(out)))])
        return [out]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--data",type=Path,default=ROOT/"data")
    args=parser.parse_args()
    args.data.mkdir(mode=0o700,parents=True,exist_ok=True)
    keyfile=args.data/"accounts.json"
    if not keyfile.exists():
        with os.fdopen(os.open(keyfile,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),"w") as f:
            json.dump({u:secrets.token_urlsafe(12) for u in store.CUSTOMERS+store.OFFICERS},f,indent=2)
    app=Application(args.data/"loan.sqlite",json.loads(keyfile.read_text()))
    with make_server("127.0.0.1",args.port,app) as server:
        print(f"Loan Desk: http://127.0.0.1:{server.server_port}\nDemo account passwords: {keyfile}",flush=True)
        server.serve_forever()

if __name__=="__main__":
    main()
