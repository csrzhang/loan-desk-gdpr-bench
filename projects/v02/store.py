"""SQLite state and transactional product operations. All amounts are synthetic EUR."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

CUSTOMERS = ("alice", "ben")
OFFICERS = ("morgan", "sam")
NOTICE = """Loan Desk Research (controller), privacy@loandesk.example, processes contact email, amount, term and income band to handle your requested application and contract. Your assigned officer may consult a synthetic Income Registry confirmation for underwriting only. The optional automatic route uses your separate explicit consent: amounts above the income-band limit are declined, which closes this application. The low, medium and high limits are EUR 5,000, 15,000 and 30,000. Manual review has the same terms and access. You can withdraw before decision, give your view, contest a decline and obtain human review. Repayment insights and promotions each require a separate optional consent. Switch either off at any time as easily as switching it on. You may object to all direct marketing. Withdrawal applies to future processing. Only authorized case staff and you can view your file. On request a local receiving controller can receive your portable fields. No international transfer is modeled. Active cases are retained for handling and servicing; an abandoned case with no remaining retention ground can be erased. Account choices remain for preference handling. You can access, correct, restrict, erase or port eligible data here, contact the controller, or complain to your EU supervisory authority. Required application fields enable assessment and delivery of your offer; without them we cannot process the application."""
LIMITS = {"low": 5000, "medium": 15000, "high": 30000}
VERSION = "2026-11-v1"

class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

def require(ok, message, status=400):
    if not ok:
        raise Problem(message, status)

@contextmanager
def database(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        with db:
            yield db
    finally:
        db.close()

def setup(path):
    with database(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, officer TEXT,
          email TEXT, amount INTEGER, term INTEGER, income TEXT, confirmed TEXT, route TEXT,
          stage TEXT, restricted INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS summaries(cid INTEGER PRIMARY KEY REFERENCES cases ON DELETE CASCADE, title TEXT);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, cid INTEGER REFERENCES cases ON DELETE CASCADE,
          kind TEXT, body TEXT, at TEXT);
        CREATE TABLE IF NOT EXISTS choices(id INTEGER PRIMARY KEY, owner TEXT, purpose TEXT, value INTEGER, version TEXT, at TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, cid INTEGER REFERENCES cases ON DELETE CASCADE,
          kind TEXT, state TEXT DEFAULT 'queued');
        CREATE TABLE IF NOT EXISTS receiver(id INTEGER PRIMARY KEY, owner TEXT, payload TEXT);
        """)

def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql,args)]

def event(db, cid, kind, body):
    db.execute("INSERT INTO events(cid,kind,body,at) VALUES(?,?,?,?)",
               (cid,kind,body,datetime.now(timezone.utc).isoformat()))

def get_case(db, who, cid):
    row = db.execute("SELECT * FROM cases WHERE id=? AND (owner=? OR officer=?)",(cid,who,who)).fetchone()
    require(row, "Case unavailable.", 404)
    return dict(row)

def email(value):
    import re
    require(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",value) and len(value)<=254,"Enter a contact email.")
    return value

def submit(db, who, data):
    require(who in CUSTOMERS,"Borrower account required.",403)
    require(set(data) <= {"email","amount","term","income","auto"},"Unexpected application field.")
    try:
        amount, term = int(data.get("amount","")), int(data.get("term",""))
    except ValueError:
        raise Problem("Enter a valid amount and term.")
    require(100 <= amount <= 100000 and term in (6,12,24,36),"Amount or term outside available range.")
    income = data.get("income","")
    require(income in LIMITS and data.get("auto","") in ("","yes"),"Invalid application choice.")
    route = "automatic" if data.get("auto")=="yes" else "manual"
    officer = dict(zip(CUSTOMERS,OFFICERS))[who]
    cid = db.execute("INSERT INTO cases(owner,officer,email,amount,term,income,route,stage) VALUES(?,?,?,?,?,?,?,?)",
                     (who,officer,email(data.get("email","")),amount,term,income,route,"pending")).lastrowid
    db.execute("INSERT INTO summaries VALUES(?,?)",(cid,f"EUR {amount:,} · {term} months"))
    event(db,cid,"application",f"{route} route selected under notice {VERSION}")
    if route=="automatic":
        queue(db,cid,"score")
    return cid

def queue(db,cid,kind):
    db.execute("INSERT INTO jobs(cid,kind) VALUES(?,?)",(cid,kind))

def enabled(db, owner, purpose):
    row=db.execute("SELECT value FROM choices WHERE owner=? AND purpose=? ORDER BY id DESC LIMIT 1",(owner,purpose)).fetchone()
    return bool(row and row[0])

def preference(db, who, purpose, value):
    require(who in CUSTOMERS and purpose in ("insights","promotions","objection") and value in ("on","off"),"Invalid preference.")
    db.execute("INSERT INTO choices(owner,purpose,value,version,at) VALUES(?,?,?,?,?)",
               (who,purpose,int(value=="on"),VERSION,datetime.now(timezone.utc).isoformat()))
    if (purpose,value)==("insights","off") or (purpose,value) in (("promotions","off"),("objection","on")):
        kind = "report" if purpose=="insights" else "promotion"
        db.execute("UPDATE jobs SET state='cancelled' WHERE kind=? AND state='queued' AND cid IN (SELECT id FROM cases WHERE owner=?)",(kind,who))

def eligible_campaign(db,cid):
    # Audience inputs are limited to identity, current preferences and case eligibility.
    r=db.execute("SELECT owner FROM cases WHERE id=? AND restricted=0 AND stage!='abandoned'",(cid,)).fetchone()
    return bool(r and enabled(db,r[0],"promotions") and not enabled(db,r[0],"objection"))

def campaign(db, who):
    require(who in OFFICERS,"Officer account required.",403)
    for row in db.execute("SELECT id FROM cases WHERE officer=?",(who,)):
        if eligible_campaign(db,row[0]):
            queue(db,row[0],"promotion")

def offer(db,c):
    return {"case":c["id"],"to":c["email"],"amount_eur":c["amount"],"term_months":c["term"]}

def portable(c):
    require(c["stage"]=="accepted","Accept an offer to export this contract.",409)
    return {k:c[k] for k in ("email","amount","term","income")}

def access(db,c):
    cid=c["id"]
    return {"application":c,"processing_information":NOTICE,"timeline":rows(db,"SELECT kind,body,at FROM events WHERE cid=? ORDER BY id",(cid,)),
            "jobs":rows(db,"SELECT kind,state FROM jobs WHERE cid=? ORDER BY id",(cid,)),
            "preferences":rows(db,"SELECT purpose,value,version,at FROM choices WHERE owner=? ORDER BY id",(c["owner"],))}

def drain(db,c):
    cid=c["id"]
    for job in rows(db,"SELECT * FROM jobs WHERE cid=? AND state='queued' ORDER BY id",(cid,)):
        if c["restricted"]:
            continue
        kind=job["kind"]
        state="cancelled"
        if kind=="score" and c["route"]=="automatic" and c["stage"]=="pending":
            band=c["confirmed"] or c["income"]
            stage="offered" if c["amount"]<=LIMITS[band] else "declined"
            db.execute("UPDATE cases SET stage=? WHERE id=?",(stage,cid))
            event(db,cid,"decision",f"Automatic {stage}. Amount {c['amount']} compared with {band} limit {LIMITS[band]}.")
            state="done"
        elif kind=="report" and enabled(db,c["owner"],"insights") and c["stage"]!="abandoned":
            event(db,cid,"report",f"Monthly principal estimate: EUR {c['amount']/c['term']:.2f}.")
            state="done"
        elif kind=="promotion" and eligible_campaign(db,cid):
            event(db,cid,"promotion","A new loan offer is available.")
            state="done"
        db.execute("UPDATE jobs SET state=? WHERE id=?",(state,job["id"]))

def action(db,who,cid,op,data):
    c=get_case(db,who,cid)
    owner=who==c["owner"]
    staff=who==c["officer"]
    stage=c["stage"]
    if op=="drain":
        drain(db,c)
        return
    if op in ("verify","review","notify-release","release"):
        require(staff,"Assigned officer required.",403)
    else:
        require(owner,"Borrower required.",403)
    if op=="verify":
        require(stage=="pending" and not c["restricted"] and data.get("band") in LIMITS,"Pending unrestricted case required.")
        db.execute("UPDATE cases SET confirmed=? WHERE id=?",(data["band"],cid))
        event(db,cid,"partner notice",f"Income Registry supplied income band {data['band']} today for underwriting. "+NOTICE)
    elif op=="withdraw-auto":
        require(stage=="pending","Decision already made.")
        db.execute("UPDATE cases SET route='manual' WHERE id=?",(cid,))
        event(db,cid,"route","Manual review requested.")
    elif op in ("report","promotion"):
        require(stage!="abandoned","Application closed.")
        if op=="report":
            require(enabled(db,who,"insights"),"Enable optional insights first.",409)
        else:
            require(eligible_campaign(db,cid),"Outside campaign audience.",409)
        queue(db,cid,op)
    elif op=="correct":
        email(data.get("email",""))
        event(db,cid,"correction","Contact email updated.")
    elif op=="restrict":
        require(stage!="abandoned" and not c["restricted"],"Select an unrestricted live case.")
        db.execute("UPDATE cases SET restricted=1 WHERE id=?",(cid,))
        event(db,cid,"dispute","Accuracy disputed. Ordinary processing paused.")
    elif op=="notify-release":
        require(c["restricted"]==1 and data.get("reason","").strip() and data.get("band") in LIMITS,"Record verified band and finding.")
        db.execute("UPDATE cases SET restricted=2,confirmed=? WHERE id=?",(data["band"],cid))
        event(db,cid,"release notice","Verification completed. Processing will resume. "+data["reason"])
    elif op=="release":
        require(c["restricted"]==2,"Notify the applicant before lifting the restriction.",409)
        db.execute("UPDATE cases SET restricted=0 WHERE id=?",(cid,))
        event(db,cid,"release","Restriction lifted.")
    elif op=="appeal":
        require(stage=="declined" and data.get("statement","").strip(),"A decline and a statement are required.")
        event(db,cid,"appeal",data["statement"])
        db.execute("UPDATE cases SET stage='contested' WHERE id=?",(cid,))
    elif op=="review":
        require(not c["restricted"] and (stage=="contested" or (stage=="pending" and c["route"]=="manual")),"Case unavailable for human determination.")
        result=data.get("result")
        require(result in ("offered","declined") and data.get("reason","").strip(),"Choose an outcome and explain your assessment.")
        db.execute("UPDATE cases SET stage=? WHERE id=?",(stage if stage=="contested" else result,cid))
        event(db,cid,"decision",f"{who} reviewed: {result}. "+data["reason"])
    elif op=="accept":
        require(stage=="offered" and not c["restricted"],"An available offer is required.")
        db.execute("UPDATE cases SET stage='accepted' WHERE id=?",(cid,))
        event(db,cid,"contract","Offer accepted.")
    elif op=="transfer":
        require(data.get("destination")=="Local Credit Union","Select the receiving controller.")
        db.execute("INSERT INTO receiver(owner,payload) VALUES(?,?)",(who,json.dumps(portable(c))))
        event(db,cid,"transfer","Delivered to Local Credit Union at your request.")
    elif op=="abandon":
        require(stage in ("pending","declined","offered") and not c["restricted"],"This case cannot be abandoned.",409)
        db.execute("UPDATE cases SET stage='abandoned' WHERE id=?",(cid,))
        db.execute("UPDATE jobs SET state='cancelled' WHERE cid=? AND state='queued'",(cid,))
        event(db,cid,"closure","Application abandoned.")
    elif op=="erase":
        require(stage=="abandoned","Only abandoned applications qualify in this scenario.",409)
        db.execute("DELETE FROM cases WHERE id=?",(cid,))
    else:
        raise Problem("Unknown action.",404)
