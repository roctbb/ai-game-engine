"""Atomic Redis transitions. Lease generations fence off replaced workers."""

ENQUEUE = """
local run = ARGV[1]
local inserted = redis.call('SADD', KEYS[3], run)
redis.call('HSET', KEYS[5], run, ARGV[2])
if not redis.call('HGET', KEYS[4], run) then
  if redis.call('SADD', KEYS[2], run) == 1 or not redis.call('LPOS', KEYS[1], run) then redis.call('RPUSH', KEYS[1], run) end
end
return inserted
"""

PULL = """
local worker, now, ttl = ARGV[1], tonumber(ARGV[2]), tonumber(ARGV[3])
if ARGV[6] == '1' then
  local leases = redis.call('HGETALL', KEYS[4])
  for i=1,#leases,2 do
    local run, lease = leases[i], cjson.decode(leases[i+1])
    if now >= (lease.expires_at or lease.leased_at + ttl) then
      redis.call('HDEL', KEYS[4], run)
      redis.call('HDEL', 'agp:worker:' .. lease.worker_id .. ':leases', run)
      if redis.call('SISMEMBER', KEYS[3], run) == 1 and redis.call('SADD', KEYS[2], run) == 1 then
        redis.call('RPUSH', KEYS[1], run)
      end
    end
  end
end
local labels = cjson.decode(ARGV[4])
local depth = redis.call('LLEN', KEYS[1])
for i=1,depth do
  local run = redis.call('LPOP', KEYS[1])
  if redis.call('SISMEMBER', KEYS[3], run) == 1 and not redis.call('HGET', KEYS[4], run) then
    local requirements = cjson.decode(redis.call('HGET', KEYS[5], run) or '{}')
    local matches = true
    for k,v in pairs(requirements) do if labels[k] ~= v then matches = false end end
    if matches then
      redis.call('SREM', KEYS[2], run)
      local clock = redis.call('TIME')
      local wall = tonumber(clock[1]) * 1000000 + tonumber(clock[2])
      local previous = tonumber(redis.call('GET', KEYS[6]) or '0')
      local generation = string.format('%.0f', math.max(wall, previous + 1))
      redis.call('SET', KEYS[6], generation)
      local lease = cjson.encode({run_id=run, worker_id=worker, lease_id=ARGV[5], leased_at=now,
        expires_at=now+ttl, generation=generation})
      redis.call('HSET', KEYS[4], run, lease)
      redis.call('HSET', 'agp:worker:' .. worker .. ':leases', run, lease)
      return lease
    end
    redis.call('RPUSH', KEYS[1], run)
  else
    redis.call('SREM', KEYS[2], run)
  end
end
return false
"""

ACK = """
local raw = redis.call('HGET', KEYS[4], ARGV[1])
if not raw then return 0 end
local lease = cjson.decode(raw)
if lease.worker_id ~= ARGV[2] or lease.lease_id ~= ARGV[3] then return 0 end
redis.call('HDEL', KEYS[4], ARGV[1])
redis.call('HDEL', 'agp:worker:' .. lease.worker_id .. ':leases', ARGV[1])
redis.call('HDEL', KEYS[5], ARGV[1])
redis.call('SREM', KEYS[3], ARGV[1])
redis.call('SREM', KEYS[2], ARGV[1])
redis.call('LREM', KEYS[1], 0, ARGV[1])
return 1
"""

RENEW = """
local raw = redis.call('HGET', KEYS[4], ARGV[1])
if not raw then return 0 end
local lease = cjson.decode(raw)
local now, ttl = tonumber(ARGV[4]), tonumber(ARGV[5])
if lease.worker_id ~= ARGV[2] or lease.lease_id ~= ARGV[3] or now >= (lease.expires_at or lease.leased_at+ttl) then return 0 end
lease.leased_at, lease.expires_at = now, now+ttl
local value = cjson.encode(lease)
redis.call('HSET', KEYS[4], ARGV[1], value)
redis.call('HSET', 'agp:worker:' .. lease.worker_id .. ':leases', ARGV[1], value)
return 1
"""

CANCEL = """
local raw = redis.call('HGET', KEYS[4], ARGV[1])
if raw then
  local lease = cjson.decode(raw)
  redis.call('HDEL', 'agp:worker:' .. lease.worker_id .. ':leases', ARGV[1])
end
redis.call('HDEL', KEYS[4], ARGV[1])
redis.call('HDEL', KEYS[5], ARGV[1])
redis.call('SREM', KEYS[3], ARGV[1])
redis.call('SREM', KEYS[2], ARGV[1])
redis.call('LREM', KEYS[1], 0, ARGV[1])
return 1
"""
