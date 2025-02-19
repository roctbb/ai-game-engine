from tasks import send
timeout = 10000 #get from msg later
code = """def test(a):\n    return a"""
function = "test"
args = 'abcd'
result = send.delay(code, function, args, timeout)
print(result.get(timeout=1))