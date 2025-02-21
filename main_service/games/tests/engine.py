import ge_sdk as sdk
import time


def game():
    code = []
    codestr = '''
import time
def skibibi(x, y):
    time.sleep(1.5)
    return x + y
    '''
    for _ in range(5):
        code.append(codestr)


if __name__ == "__main__":
    game()
