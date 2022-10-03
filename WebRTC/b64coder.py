import json
import base64


def json_b64encode(json_dict):
    jsonstr = json.dumps(json_dict) # dict --> str
    encoded = base64.b64encode(jsonstr.encode('utf-8'))  # 1 way
    # print(base64.encodebytes(datastr.encode()))  # 2 method

    return encoded

def b64decode(b64_encoded):
    b64decoded = base64.b64decode(b64_encoded)  # 1 way
    # decoded = base64.decodebytes(b64_encoded.decode()) # 2 method
    # decoded = b64decoded.decode('utf-8')
    decoded = json.loads(b64decoded.decode('utf-8'))

    return decoded

if __name__ == '__main__':
    with open('../test/answer.json') as jsonfile:
        data = json.load(jsonfile)
        encoded = json_b64encode(data)
        decoded = b64decode(encoded)
        print("b64enc: {} \n b64dec: {}".format( encoded, decoded))
