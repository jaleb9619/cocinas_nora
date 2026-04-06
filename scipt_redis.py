# python3 scipt_redis.py

import redis

r = redis.Redis(
    host='redis-12806.c82.us-east-1-2.ec2.cloud.redislabs.com',
    port=12806,
    decode_responses=True,
    username="default",
    password="2FzxV57BBTXxM6ERmu0eTts4V1DgdoRL",
)

success = r.set('foo', 'bar')
# True

result = r.get('foo')
print(result)
# >>> bar

