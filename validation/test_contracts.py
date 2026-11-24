"""Exercise the WSGI entry point with browser-style forms, sessions and actual SQLite."""
import io
import json
import re
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from app import Application

PASSWORDS={name:"fixture-"+name for name in ("alice","ben","morgan","sam")}

class Client:
    def __init__(self, app, name):
        self.app=app
        self.cookie=""
        self.token=""
        self.post("/login",{"user":name,"password":PASSWORDS[name]})
        self.token=re.search(r'name="csrf" value="([^"]+)"',self.get("/"))[1]

    def request(self,path,fields=None,status=200):
        body=urlencode(fields or {}).encode()
        env={"REQUEST_METHOD":"GET" if fields is None else "POST","PATH_INFO":path,
             "HTTP_HOST":"localhost","HTTP_COOKIE":self.cookie,"wsgi.input":io.BytesIO(body),
             "CONTENT_TYPE":"application/x-www-form-urlencoded","CONTENT_LENGTH":str(len(body))}
        def response(s,headers):
            self.status=int(s.split()[0])
            self.headers=dict(headers)
        out=b"".join(self.app(env,response)).decode()
        if self.status!=status:
            raise AssertionError(f"{path}: expected {status}, got {self.status}: {out[:1000]}")
        if "Set-Cookie" in self.headers:self.cookie=self.headers["Set-Cookie"].split(";")[0]
        return out

    def get(self,path,status=200):
        return self.request(path,status=status)

    def post(self,path,fields=None,status=303):
        self.request(path,{"csrf":self.token,**(fields or {})},status)
        return self.headers.get("Location")

    def apply(self,**changes):
        return self.post("/apply",{"email":"person@example.test","income":"medium","term":"12","amount":"9000",**changes})

    def choice(self,purpose,value):
        self.post("/preference",dict(purpose=purpose,value=value))

    def copy(self,case):
        return json.loads(self.get(case+"/access"))

    def timeline(self,case,kind):
        return [e["body"] for e in self.copy(case)["timeline"] if e["kind"]==kind]

class LoanContracts(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/"test.sqlite"
        self.restart()

    def restart(self):
        self.app=Application(self.path,PASSWORDS)
        self.a,self.b,self.o,self.s=[Client(self.app,n) for n in PASSWORDS]

    def query(self,sql,params=()):
        db=sqlite3.connect(self.path)
        try:return db.execute(sql,params).fetchall()
        finally:db.close()

    def offered(self):
        case=self.a.apply(auto="yes")
        self.a.post(case+"/drain")
        return case

    def test_GDPR01_minimum_application_fields(self):
        form=self.a.get("/").split('action="/apply"')[1].split("</form>")[0]
        self.assertEqual(set(re.findall(r'name="([^"]+)"',form)),{"csrf","amount","term","email","income","auto"})
        case=self.a.apply()
        self.a.post("/apply",{"email":"alice@example.test","income":"low","amount":"1000","term":"6","hobby":"red canoe"},400)
        self.assertEqual(self.query("select count(*) from cases"),[(1,)])
        self.assertNotIn("red canoe",json.dumps(self.a.copy(case)))
        self.assertNotIn("hobby",[r[1] for r in self.query("pragma table_info(cases)")])

    def test_GDPR02_underwriting_and_campaign_inputs(self):
        self.a.choice("promotions","on")
        case=self.a.apply(auto="yes",income="high")
        self.o.post(case+"/verify",{"band":"low"})
        # Inspect actual targeting reads using SQLite authorizer and the ordinary HTTP action.
        from unittest.mock import patch
        connect=sqlite3.connect
        reads=set()
        def observed(*args,**kw):
            db=connect(*args,**kw)
            def log(op,table,column,*_):
                if op==sqlite3.SQLITE_READ:reads.add((table,column))
                return sqlite3.SQLITE_OK
            db.set_authorizer(log)
            return db
        with patch("sqlite3.connect",observed):self.o.post("/campaign")
        self.assertTrue({("choices","purpose"),("cases","owner")}<=reads)
        self.assertFalse({("cases","income"),("cases","confirmed")}&reads)
        self.a.post(case+"/drain")
        self.assertEqual(self.a.copy(case)["application"]["stage"],"declined")
        self.assertEqual(len(self.a.timeline(case,"promotion")),1)

    def test_GDPR03_specific_optional_choice(self):
        case=self.a.apply()
        self.a.post(case+"/report",status=409)
        self.a.choice("promotions","on")
        self.a.post(case+"/report",status=409)
        self.a.choice("insights","on")
        self.a.post(case+"/report")
        self.a.post(case+"/drain")
        self.assertEqual(len(self.a.timeline(case,"report")),1)
        self.assertTrue(any(p["purpose"]=="insights" and p["version"] and p["value"] for p in self.a.copy(case)["preferences"]))

    def test_GDPR04_withdraw_after_enqueue_and_retry(self):
        cases=[x.apply() for x in (self.a,self.b)]
        for x,c in zip((self.a,self.b),cases):
            x.choice("insights","on")
            x.post(c+"/report")
        self.a.choice("insights","off")
        self.restart()
        for x,c,n in zip((self.a,self.b),cases,(0,1)):
            for _ in range(2):x.post(c+"/drain")
            self.assertEqual(len(x.timeline(c,"report")),n)

    def test_GDPR05_direct_and_indirect_notice(self):
        page=self.a.get("/")
        for phrase in ("Loan Desk Research","supervisory authority","withdraw","Income Registry","international transfer"):
            self.assertIn(phrase,page)
        self.assertLess(page.index("How we use"),page.index('name="email"'))
        for client,staff,contact in ((self.a,self.o,True),(self.b,self.s,False)):
            case=client.apply()
            before=datetime.now(timezone.utc)
            staff.post(case+"/verify",{"band":"medium"})
            after=datetime.now(timezone.utc)
            if contact:client.get(case)
            # Inspect delivery on import, even if the customer never opens the inbox.
            body,at=self.query("select body,at from events where kind='partner notice' and cid=?",(case.split("/")[-1],))[0]
            self.assertTrue(before<=datetime.fromisoformat(at)<=after)
            self.assertIn("Income Registry supplied income band medium",body)
            self.assertIn("controller",body)

    def test_GDPR06_access_inventory_and_owner(self):
        c=self.a.apply(auto="yes")
        self.b.apply(email="ben-only@example.test")
        self.o.post(c+"/verify",{"band":"low"})
        self.a.post(c+"/drain")
        result=self.a.copy(c)
        self.assertEqual((result["application"]["amount"],result["application"]["confirmed"]),(9000,"low"))
        self.assertTrue(self.a.timeline(c,"decision"))
        self.assertTrue(self.a.timeline(c,"partner notice"))
        self.assertIn("retained",result["processing_information"])
        self.assertNotIn("ben-only",json.dumps(result))
        self.b.get(c+"/access",404)

    def test_GDPR07_correct_and_regenerate_offer(self):
        c=self.offered()
        other=self.b.apply()
        self.a.post(c+"/correct",{"email":"new@example.test"})
        self.restart()
        self.assertEqual(json.loads(self.a.get(c+"/offer"))["to"],"new@example.test")
        self.assertEqual(self.b.copy(other)["application"]["email"],"person@example.test")

    def test_GDPR08_erase_main_copies_jobs_and_replay(self):
        c=self.a.apply(auto="yes")
        cid=int(c.split("/")[-1])
        active=self.a.apply()
        self.a.post(active+"/erase",status=409)
        self.a.post(c+"/abandon")
        self.a.post(c+"/erase")
        self.restart()
        self.a.post(c+"/drain",status=404)
        self.a.get(c,404)
        for table,field in (("cases","id"),("summaries","cid"),("events","cid"),("jobs","cid")):
            self.assertFalse(self.query(f"select 1 from {table} where {field}=?",(cid,)))
        self.assertIn(active,self.a.get("/"))

    def test_GDPR09_dispute_pause_notify_then_resume(self):
        c=self.a.apply(auto="yes")
        self.o.post(c+"/verify",{"band":"low"})
        self.a.post(c+"/restrict")
        self.o.post(c+"/release",status=409)
        for _ in range(2):self.a.post(c+"/drain")
        self.assertFalse(self.a.timeline(c,"decision"))
        self.assertEqual(self.a.copy(c)["application"]["confirmed"],"low")
        self.o.post(c+"/notify-release",{"band":"medium","reason":"Confirmation corrected by registry."})
        self.assertTrue(self.a.timeline(c,"release notice"))
        self.a.post(c+"/drain")
        self.assertFalse(self.a.timeline(c,"decision"))
        self.o.post(c+"/release")
        self.a.post(c+"/drain")
        self.assertEqual(self.a.copy(c)["application"]["stage"],"offered")

    def test_GDPR10_portable_contract_and_receiver(self):
        c=self.offered()
        self.a.get(c+"/portable",409)
        self.a.post(c+"/accept")
        expected={"amount":9000,"term":12,"income":"medium","email":"person@example.test"}
        self.assertEqual(json.loads(self.a.get(c+"/portable")),expected)
        self.b.get(c+"/portable",404)
        self.a.post(c+"/transfer",{"destination":"Local Credit Union"})
        deliveries=self.query("select owner,payload from receiver")
        self.assertEqual([(u,json.loads(p)) for u,p in deliveries],[("alice",expected)])

    def test_GDPR11_object_to_marketing_keep_service(self):
        c=self.a.apply(auto="yes")
        d=self.b.apply()
        for x,off in [(self.a,self.o),(self.b,self.s)]:
            x.choice("promotions","on")
            off.post("/campaign")
        self.a.choice("objection","on")
        self.o.post("/campaign")
        self.a.post(c+"/promotion",status=409)
        self.a.post(c+"/drain")
        self.b.post(d+"/drain")
        self.assertFalse(self.a.timeline(c,"promotion"))
        self.assertEqual(len(self.b.timeline(d,"promotion")),1)
        self.assertTrue(self.a.timeline(c,"decision"))
        self.assertEqual(len([j for j in self.a.copy(c)["jobs"] if j["kind"]=="promotion"]),1)

    def test_GDPR12_case_and_document_isolation(self):
        c=self.offered()
        for suffix in ("","/offer"):
            for x in (self.a,self.o):self.assertTrue(x.get(c+suffix))
            for x in (self.b,self.s):self.assertNotIn("person@example.test",x.get(c+suffix,404))
        self.a.post(c+"/review",{"reason":"x","result":"offered"},403)
        self.a.post(c+"/abandon",{"csrf":"wrong"},403)
        self.a.post("/logout")
        self.a.get(c,401)

    def test_GDPR13_real_decision_appeal_and_manual_alternative(self):
        c=self.a.apply(auto="yes",income="low")
        self.a.post(c+"/drain")
        self.a.get(c+"/offer",409)
        self.a.post(c+"/appeal",{"statement":"The documentation of my income was incomplete."})
        self.assertIn("documentation",self.o.get(c))
        self.s.post(c+"/review",{"reason":"test","result":"offered"},404)
        self.o.post(c+"/review",{"reason":"Independently reviewed revised documentation.","result":"offered"})
        self.assertEqual(json.loads(self.a.get(c+"/offer"))["amount_eur"],9000)
        self.assertEqual(len(self.a.timeline(c,"decision")),2)
        manual=self.a.apply()
        withdrawn=self.a.apply(auto="yes")
        self.a.post(withdrawn+"/withdraw-auto")
        for path in (manual,withdrawn):
            self.a.post(path+"/drain")
            self.assertFalse(self.a.timeline(path,"decision"))
            self.o.post(path+"/review",{"reason":"Verified application.","result":"offered"})
            self.assertEqual(json.loads(self.a.get(path+"/offer"))["term_months"],12)

if __name__=="__main__":
    unittest.main()
