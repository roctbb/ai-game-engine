from tasks import send
timeout = 10000 #get from msg later
code = """def test(a):\n    return a"""
function = "test"
args = 'abcd'
result = send.delay(code, function, args, timeout)
output = result.get(timeout=5)['run']['output']
print(output)