"""Collect behavior from one isolated snapshot. stdout is stable JSON for replay."""
import argparse
import json
import sys
import unittest
from pathlib import Path

def measure(t, oid):
    alice, ben, officer = t.a, t.b, t.o
    if oid == 'GDPR01':
        path = alice.apply()
        alice.post('/apply', dict(email='a@example.test', term='12', income='medium', amount='9000', hobby='painting'), 400)
        return dict(eligible_application=path, after_extra_field=t.query('select count(*) from cases')[0][0])
    if oid == 'GDPR02':
        path = alice.apply(auto='yes', income='high')
        officer.post(path+'/verify', {'band':'low'})
        alice.choice('promotions','on')
        officer.post('/campaign')
        alice.post(path+'/drain')
        return dict(decisions=alice.timeline(path,'decision'), promotions=len(alice.timeline(path,'promotion')))
    if oid == 'GDPR03':
        path = alice.apply()
        alice.post(path+'/report', status=409)
        before = len(alice.timeline(path,'report'))
        alice.choice('insights','on')
        alice.post(path+'/report')
        alice.post(path+'/drain')
        return dict(before_opt_in=before, after_opt_in=len(alice.timeline(path,'report')),
                    choice_version=alice.copy(path)['preferences'][0]['version'])
    if oid == 'GDPR04':
        a,b = alice.apply(),ben.apply()
        for user,case in [(alice,a),(ben,b)]:
            user.choice('insights','on')
            user.post(case+'/report')
        alice.choice('insights','off')
        t.restart()
        for user,case in [(t.a,a),(t.b,b)]:
            for _ in range(2):
                user.post(case+'/drain')
        return dict(withdrawn_reports=len(t.a.timeline(a,'report')), control_reports=len(t.b.timeline(b,'report')),
                    withdrawn_job=t.a.copy(a)['jobs'][0]['state'])
    if oid == 'GDPR05':
        path=alice.apply()
        officer.post(path+'/verify',{'band':'medium'})
        notice = alice.timeline(path,'partner notice')[0]
        return dict(source_named='Income Registry supplied income band medium' in notice,
                    direct_notice_before_input=alice.get('/').index('How we use')<alice.get('/').index('name="email"'))
    if oid == 'GDPR06':
        path=alice.apply(auto='yes')
        officer.post(path+'/verify',{'band':'low'})
        alice.post(path+'/drain')
        copy=alice.copy(path)
        return dict(copy_sections=sorted(copy), confirmed_income=copy['application']['confirmed'],
                    event_kinds=[e['kind'] for e in copy['timeline']])
    if oid == 'GDPR07':
        path=t.offered()
        original=json.loads(alice.get(path+'/offer'))['to']
        alice.post(path+'/correct',{'email':'new@example.test'})
        t.restart()
        return dict(original=original,requested='new@example.test',receipt=t.a.timeline(path,'correction'),
                    stored=t.a.copy(path)['application']['email'], next_offer=json.loads(t.a.get(path+'/offer'))['to'])
    if oid == 'GDPR08':
        path=alice.apply(auto='yes')
        active=alice.apply()
        alice.post(path+'/abandon')
        alice.post(path+'/erase')
        t.restart()
        counts={table:t.query('SELECT count(*) FROM '+table+' WHERE '+key+'=?',(int(path.split('/')[-1]),))[0][0]
                for table,key in [('cases','id'),('summaries','cid'),('events','cid'),('jobs','cid')]}
        return dict(rows_after_restart=counts,active_visible=active in t.a.get('/'))
    if oid == 'GDPR09':
        path=alice.apply(auto='yes')
        officer.post(path+'/verify',{'band':'low'})
        alice.post(path+'/restrict')
        alice.post(path+'/drain')
        copy=alice.copy(path)
        return dict(restriction=copy['application']['restricted'], disputed_band=copy['application']['confirmed'],
                    effective_stage=copy['application']['stage'],decision_events=alice.timeline(path,'decision'))
    if oid == 'GDPR10':
        path=t.offered()
        alice.post(path+'/accept')
        local=json.loads(alice.get(path+'/portable'))
        alice.post(path+'/transfer',{'destination':'Local Credit Union'})
        payload=t.query('SELECT payload FROM receiver WHERE owner=?',('alice',))[0][0]
        return dict(provided_term=12,download=local,received=json.loads(payload))
    if oid == 'GDPR11':
        observed={}
        for user,staff,who in [(alice,officer,'objector'),(ben,t.s,'subscriber')]:
            path=user.apply(auto='yes')
            user.choice('promotions','on')
            staff.post('/campaign')
            if who=='objector':
                user.choice('objection','on')
                staff.post('/campaign')
            user.post(path+'/drain')
            observed[who]=dict(promotions=len(user.timeline(path,'promotion')), decisions=len(user.timeline(path,'decision')))
        return observed
    if oid == 'GDPR12':
        path=t.offered()
        statuses={}
        for who,user,expected in [('owner',alice,200),('assigned',officer,200),('other',ben,404),('unassigned',t.s,404)]:
            statuses[who]=[]
            for suffix in ('','/offer'):
                user.get(path+suffix,expected)
                statuses[who].append(user.status)
        return dict(routes=['case','offer'],responses=statuses)
    if oid == 'GDPR13':
        path=alice.apply(auto='yes',income='low')
        alice.post(path+'/drain')
        alice.post(path+'/appeal',{'statement':'Please consider updated documentation.'})
        officer.post(path+'/review',{'result':'offered','reason':'Documents reviewed.'})
        record=alice.copy(path)
        # Use raw WSGI result, including status, even if delivery fails.
        from wsgiref.util import setup_testing_defaults
        env={}
        setup_testing_defaults(env)
        env.update(PATH_INFO=path+'/offer',HTTP_HOST='localhost',HTTP_COOKIE=alice.cookie)
        status=[]
        response=b''.join(t.app(env,lambda code,headers:status.append(int(code.split()[0]))))
        return dict(review_log=alice.timeline(path,'decision')[-1],stage=record['application']['stage'],
                    download_status=status[0],offer_amount=json.loads(response)['amount_eur'] if status[0]==200 else None)
    raise KeyError(oid)

def collect(project):
    sys.path.insert(0,str(project.resolve()))
    from test_contracts import LoanContracts
    import app
    if Path(app.__file__).resolve().parent != project.resolve():
        raise RuntimeError('Wrong application import')
    results={}
    for name in unittest.defaultTestLoader.getTestCaseNames(LoanContracts):
        oid=name.split('_')[1]
        result=unittest.TestResult()
        LoanContracts(name).run(result)
        if result.errors or result.skipped or result.testsRun != 1:
            raise RuntimeError((name,result.errors,result.skipped))
        fixture=LoanContracts(name)
        fixture.setUp()
        try:
            obs=measure(fixture,oid)
        finally:
            fixture.doCleanups()
        results[oid]=dict(test=name, contract='FAIL' if result.failures else 'PASS',
                          failure=result.failures[0][1].splitlines()[-1] if result.failures else None,
                          observed=obs)
    if len(results)!=13:
        raise RuntimeError('Incomplete suite')
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('project',type=Path)
    print(json.dumps(collect(parser.parse_args().project),indent=2,sort_keys=True))
