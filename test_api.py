import urllib.request, json

def test(label, data, expect_key='success'):
    try:
        r = urllib.request.Request('https://venerable-froyo-1ed9bb.netlify.app/api/save-article', data=json.dumps(data).encode(), headers={'Content-Type':'application/json'}, method='POST')
        resp = urllib.request.urlopen(r, timeout=15)
        d = json.loads(resp.read())
        ok = expect_key in str(d)
        print(label, 'OK' if ok else 'FAIL', str(d)[:80])
        return d if ok else None
    except Exception as e:
        print(label, 'ERROR', str(e)[:80])
        return None

print('=== Testing API ===')
test('Create', {'action':'save','type':'article','slug':'test001','title':'Test Article','date':'2026-07-03','series':'Test','cover':'gradient-ocean','tags':['test'],'excerpt':'x','content':'## Hello\nTest.'})
test('List  ', {'action':'list','type':'article'}, '[')
test('Get   ', {'action':'get','type':'article','slug':'test001'}, 'title')
test('Del   ', {'action':'delete','type':'article','slug':'test001'})
print('Done')
