TABLE_SCHEMA = """
## 可用数据表（ClickHouse logdb）

### sessions — 网络会话记录（最核心，364亿条）
字段：dev_id(UInt16), start(DateTime), end(DateTime), protocol(UInt8, 6=TCP/17=UDP/1=ICMP),
src_ipv4(IPv4), dst_ipv4(IPv4), src_port(UInt16), dst_port(UInt16),
up_bytes(UInt64), down_bytes(UInt64), up_pkts(UInt32), down_pkts(UInt32),
ret_up_pkts(UInt32), ret_down_pkts(UInt32),
wan_name(String), appid(UInt32), domain_name(String), account(String),
src_ISP(String), dst_ISP(String), dst_pos_country(String), dst_pos_province(String),
malc_hit(UInt8), direction(UInt8)
注意：查询必须带 start 时间条件，时间范围>7天需按天分片

### npm — 网络性能监控（375亿条）
字段：start(DateTime), end(DateTime), src_ipv4(IPv4), dst_ipv4(IPv4),
clntdelay(UInt32,μs), svrdelay(UInt32,μs), appdelay(UInt32,μs),
ret_up_pkts(UInt32), ret_down_pkts(UInt32), wan_name(String), malc_hit(UInt8)
注意：查询必须带 start 时间条件

### dns — DNS查询日志（34亿条）
字段：collect_time(DateTime), src_ipv4(IPv4), src_mac(String),
dst_ipv4(IPv4), domain_name(String), account(String)
注意：查询必须带 collect_time 时间条件

### url — HTTP/HTTPS访问日志（26亿条）
字段：collect_time(DateTime), type(String), uri(String), domain_name(String),
src_ipv4(IPv4), dst_ipv4(IPv4), appid(UInt32), account(String)
注意：查询必须带 collect_time 时间条件

### iplog — IP流量汇总（10亿条，按IP聚合，60s间隔）
字段：collect_time(DateTime), interval(UInt32), ipv4(IPv4),
up_bytes(UInt64), down_bytes(UInt64), flowcnt(UInt32), appid(UInt32), account(String)

### wanlog — WAN出口流量统计（119万条，60s间隔）
字段：collect_time(DateTime), interval(UInt32), wan_name(String),
wan_id(UInt32), wan_type(UInt8), in_bps(UInt64), out_bps(UInt64)

### applog — 应用流量汇总（3330万条）
字段：collect_time(DateTime), interval(UInt32), appid(UInt32),
up_bytes(UInt64), down_bytes(UInt64), flowcnt(UInt32)

### event — 应用事件（1.9亿条）
字段：type(String, qqlogin3/weixin3/pop3login3), collect_time(DateTime),
account(String), src_ipv4(IPv4), src_mac(String), app_account(String)

### usrauth — 用户认证记录（14万条）
字段：collect_time(DateTime), account(String), src_ipv4(IPv4),
src_mac(String), logtype(String, login/logoff)

## SQL规则
1. 所有查询必须包含时间条件（sessions/npm用start，其余用collect_time）
2. 只允许SELECT语句
3. 大表（sessions/npm/dns/url）建议加 LIMIT 10000
4. 时间范围超过7天时，建议按天分片查询
"""
