import sandbox_run

timeout = 10000 #get from msg later
code = """def test(a):\n    return a"""
function = "test"
args = 'abcd'
result = sandbox_run.start_execute(code, function, [args], timeout)
print(result)