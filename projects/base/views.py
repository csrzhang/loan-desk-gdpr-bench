"""Server-rendered customer and officer workspace."""
from html import escape
from store import NOTICE, CUSTOMERS, enabled

def h(v):
    return escape(str(v), quote=True)

def page(title, content, who="", tenant="Loan Desk"):
    identity=f'<span class="user">{h(who)}</span>' if who else ''
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{h(title)} · Loan Desk</title><link rel="stylesheet" href="/style.css"><header><nav><a class="brand" href="/">Loan Desk</a><span>Application workspace</span>{identity}</nav></header><main>{content}</main></html>'''

def form(url,token,button,fields="",css=""):
    return f'<form method="post" class="{css}" action="{url}"><input type="hidden" name="csrf" value="{h(token)}">{fields}<button>{h(button)}</button></form>'

def inputbox(label,name,kind="text",extra=""):
    return f'<label>{label}<input type="{kind}" name="{name}" required {extra}></label>'

def select(label,name,options):
    return f'<label>{label}<select name="{name}">'+''.join(f'<option>{h(x)}</option>' for x in options)+'</select></label>'

def login():
    return page("Sign in",'<section class="login"><div class="eyebrow">Local research application</div><h1>Loan Desk</h1><p>Sign in to manage a loan application or review an assigned case.</p>'+form("/login","","Sign in",inputbox("Demo account","user")+inputbox("Local password","password","password"))+'</section>')

def notice():
    return '<details><summary>How we use your information</summary><p>'+h(NOTICE)+'</p></details>'

def dashboard(db,who,t,cases):
    cards=''.join(f'<a class="row" href="/case/{c["id"]}"><b>LD-{c["id"]:04}</b><span>{h(c["title"])}</span><mark>{h(c["stage"])}</mark></a>' for c in cases)
    body=f'<div class="top"><div><small>Workspace / {h(who)}</small><h1>Applications</h1></div>'+form("/logout",t,"Sign out",css="quiet")+'</div><section><h2>Your casebook</h2>'+(cards or '<p>No applications yet.</p>')+'</section>'
    if who in CUSTOMERS:
        fields=notice()+inputbox("Contact email","email","email")+inputbox("Requested amount (EUR)","amount","number",'min="100" max="100000"')+select("Term in months","term",[6,12,24,36])+select("Income band","income",["low","medium","high"])
        fields+='<label class="check"><input type="checkbox" name="auto" value="yes">I explicitly choose an automatic credit decision. Amounts above the income limit may be declined. I can withdraw before the decision and contest a refusal. Leave unchecked for human review on the same terms.</label>'
        body+='<div class="grid"><section><h2>New application</h2>'+form("/apply",t,"Submit application",fields)+'</section><section><h2>Privacy choices</h2><p>Insights create a private repayment estimate. Promotions send loan offers. Both are optional. Withdraw at any time here. An objection stops all direct marketing.</p>'
        for key,label in (("insights","Repayment insights"),("promotions","Loan promotions"),("objection","Marketing objection")):
            on=enabled(db,who,key)
            body+=f'<div class="pref"><b>{label}</b><span>{"On" if on else "Off"}</span>'+form("/preference",t,"Switch off" if on else "Switch on",f'<input type="hidden" name="purpose" value="{key}"><input type="hidden" name="value" value="{"off" if on else "on"}">', "quiet")+'</div>'
        body+='</section></div>'
    else:
        body+='<section><h2>Assigned portfolio</h2>'+form("/campaign",t,"Queue campaign for eligible cases")+'</section>'
    return page("Applications",body,who)

def detail(c,t,who,events,jobs):
    cid=c['id']
    base=f"/case/{cid}"
    def act(op,title,fields=""):
        return form(base+"/"+op,t,title,fields)
    owner=who==c["owner"]
    stage=c["stage"]
    body=f'<a href="/">← Applications</a><div class="top"><div><small>Application LD-{cid:04}</small><h1>EUR {c["amount"]:,}</h1></div><mark>{h(stage)}</mark></div>'
    body+=f'<section class="facts"><b>{c["term"]} months</b> · {h(c["route"])} review · Officer {h(c["officer"])}<p>{h(c["email"])} · Declared income: {h(c["income"])} · Confirmed: {h(c["confirmed"] or "pending")} · Processing: {"restricted" if c["restricted"] else "open"}</p></section>'
    business=''
    if owner:
        if stage=="pending" and c["route"]=="automatic": business+=act("withdraw-auto","Switch to manual review")
        if stage=="declined": business+=act("appeal","Request human review",inputbox("Your statement","statement"))
        if stage in ("offered","accepted"):
            business+=f'<p><a href="{base}/offer">Download current offer</a></p>'
        if stage=="offered": business+=act("accept","Accept loan offer")
        if stage not in ("abandoned","accepted","contested"): business+=act("abandon","Abandon application")
    else:
        if stage=="pending": business+=act("verify","Import partner confirmation",select("Income Registry band","band",["low","medium","high"]))
        if stage=="contested" or (stage=="pending" and c["route"]=="manual"):
            business+=act("review","Record human decision",select("Decision","result",["offered","declined"])+inputbox("Assessment and reasons","reason"))
        if c["restricted"]==1:business+=act("notify-release","Deliver advance notice",select("Verified income band","band",["low","medium","high"])+inputbox("Verification finding","reason"))
        if c["restricted"]==2:business+=act("release","Lift notified restriction")
    controls=''
    if owner:
        controls+=f'<p><a href="{base}/access">Download access copy</a></p>'+act("correct","Save corrected email",inputbox("Correct contact email","email","email"))
        if not c["restricted"] and stage!="abandoned":controls+=act("restrict","Dispute accuracy and restrict use")
        if stage=="accepted":
            controls+=f'<p><a href="{base}/portable">Download portable JSON</a></p>'+act("transfer","Send portable data",select("Receiving controller","destination",["Local Credit Union"]))
        if stage=="abandoned":controls+=act("erase","Erase abandoned case and copies")
    worker=''
    if owner and stage!="abandoned":worker+=act("report","Queue repayment report")+act("promotion","Queue promotional message")
    worker+=act("drain","Process pending tasks")
    worker+='<ul>'+''.join(f'<li>{h(j["kind"])} · {h(j["state"])}</li>' for j in jobs)+'</ul>'
    log=''.join(f'<li><small>{h(e["at"][:19])} UTC · {h(e["kind"])}</small><p>{h(e["body"])}</p></li>' for e in reversed(events))
    body+='<div class="grid"><section><h2>Case actions</h2>'+(business or '<p>No decision action pending.</p>')+'</section>'
    if controls:body+='<section><h2>Data rights</h2>'+controls+'</section>'
    body+='</div><section><h2>Processing queue</h2>'+worker+'</section><section><h2>Case inbox &amp; history</h2><ol>'+log+'</ol></section>'
    return page("Application",body,who)
