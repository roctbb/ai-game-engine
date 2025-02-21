import ge_sdk as sdk
import time
import random

def game():
    code = []
    codestr = '''
import time
def skibidi(x, y):
    time.sleep(1.5)
    return x + y
    '''
    for _ in range(5):
        code.append(codestr)

    args = list()
    for _ in range(5):
        args.append((random.randint(1, 20), random.randint(1, 20)))

    sdk.run_multiple([{
        'code': codestr,
        'func': 'skibidi',
        'args': (1, 2),
        'timeout': 2.0,
    }])


if __name__ == "__main__":
    game()
