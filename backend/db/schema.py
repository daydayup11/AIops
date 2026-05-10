TABLE_SCHEMA = """
## 数据库：ClickHouse logdb（以下字段来自 DESCRIBE TABLE，完整且准确）

### sessions — 网络会话记录（364亿条，大表）
| 列名 | 类型 | 说明 |
|------|------|------|
| dev_id | UInt16 | 设备ID |
| probe_id | UInt16 | 探针ID |
| in_if | UInt32 | 入接口 |
| out_if | UInt32 | 出接口 |
| src_asn | UInt32 | 源ASN |
| dst_asn | UInt32 | 目标ASN |
| tcp_flags | UInt16 | TCP标志位 |
| direction | UInt8 | 方向 |
| dst_mac | String | 目标MAC |
| src_mac | String | 源MAC |
| protocol | UInt8 | 协议(6=TCP,17=UDP,1=ICMP) |
| appid | UInt32 | 应用ID |
| start | DateTime | 会话开始时间（时间分区键，必须带此条件） |
| end | DateTime | 会话结束时间 |
| up_bytes | UInt64 | 上行字节数 |
| down_bytes | UInt64 | 下行字节数 |
| ifname | String | 入接口名 |
| out_ifname | String | 出接口名 |
| src_ipv4 | IPv4 | 源IPv4地址 |
| src_port | UInt16 | 源端口 |
| dst_ipv4 | IPv4 | 目标IPv4地址 |
| dst_port | UInt16 | 目标端口 |
| src_nat_ipv4 | IPv4 | 源NAT IPv4 |
| src_nat_port | UInt16 | 源NAT端口 |
| dst_nat_ipv4 | IPv4 | 目标NAT IPv4 |
| dst_nat_port | UInt16 | 目标NAT端口 |
| up_pkts | UInt32 | 上行包数 |
| down_pkts | UInt32 | 下行包数 |
| ret_up_pkts | UInt32 | 上行重传包数 |
| ret_down_pkts | UInt32 | 下行重传包数 |
| src_ISP | String | 源ISP |
| dst_ISP | String | 目标ISP |
| domain_name | String | 域名 |
| account | String | 用户账号 |
| src_pos_country | String | 源IP所属国家 |
| src_pos_province | String | 源IP所属省份 |
| src_pos_city | String | 源IP所属城市 |
| src_pos_district | String | 源IP所属区县 |
| dst_pos_country | String | 目标IP所属国家 |
| dst_pos_province | String | 目标IP所属省份 |
| dst_pos_city | String | 目标IP所属城市 |
| dst_pos_district | String | 目标IP所属区县 |
| accgrp_name | String | 账号组名 |
| rstflag0 | UInt8 | 重置标志0 |
| rstflag1 | UInt8 | 重置标志1 |
| route_policy_id | UInt16 | 路由策略ID |
| goodflow | UInt8 | 优质流量标记 |
| vid | UInt8 | VLAN ID |
| httpcode | UInt16 | HTTP状态码 |
| httptype | UInt16 | HTTP类型 |
| ipid | UInt16 | IP ID |
| seq | UInt32 | 序列号 |
| route_policy_cookie | UInt32 | 路由策略Cookie |
| malc_hit | UInt8 | 恶意命中标记 |
| vni | UInt32 | VNI |
| wan_name | String | WAN出口名称 |
| tos | UInt8 | TOS |
| ip_precedence | UInt8 | IP优先级 |
| tos_service | UInt8 | TOS服务类型 |
| dscp | UInt8 | DSCP |
| ecn | UInt8 | ECN |
| post_tos | UInt8 | 处理后TOS |
| post_ip_precedence | UInt8 | 处理后IP优先级 |
| post_tos_service | UInt8 | 处理后TOS服务 |
| post_dscp | UInt8 | 处理后DSCP |
| post_ecn | UInt8 | 处理后ECN |
| acl_action | UInt8 | ACL动作 |
| priod_min | Float32 | 最小优先级延迟 |
| up_avg_min | UInt32 | 上行平均最小速率 |
| down_avg_min | UInt32 | 下行平均最小速率 |
⚠️ 查询必须带 start 时间条件；时间范围>7天需按天分片；必须加 LIMIT

### npm — 网络性能监控（375亿条，大表）
| 列名 | 类型 | 说明 |
|------|------|------|
| dev_id | UInt16 | 设备ID |
| probe_id | UInt16 | 探针ID |
| protocol | UInt8 | 协议 |
| appid | UInt32 | 应用ID |
| start | DateTime | 开始时间（时间分区键，必须带此条件） |
| end | DateTime | 结束时间 |
| up_bytes | UInt32 | 上行字节数 |
| down_bytes | UInt32 | 下行字节数 |
| clntdelay | UInt32 | 客户端延迟(μs) |
| svrdelay | UInt32 | 服务端延迟(μs) |
| appdelay | UInt32 | 应用延迟(μs) |
| up_pkts | UInt32 | 上行包数 |
| down_pkts | UInt32 | 下行包数 |
| ret_up_pkts | UInt32 | 上行重传包数 |
| ret_down_pkts | UInt32 | 下行重传包数 |
| src_ipv4 | IPv4 | 源IPv4 |
| src_port | UInt16 | 源端口 |
| dst_ipv4 | IPv4 | 目标IPv4 |
| dst_port | UInt16 | 目标端口 |
| src_nat_ipv4 | IPv4 | 源NAT IPv4 |
| src_nat_port | UInt16 | 源NAT端口 |
| dst_nat_ipv4 | IPv4 | 目标NAT IPv4 |
| dst_nat_port | UInt16 | 目标NAT端口 |
| domain_name | String | 域名 |
| account | String | 用户账号 |
| src_ISP | String | 源ISP |
| dst_ISP | String | 目标ISP |
| src_pos_country | String | 源IP国家 |
| src_pos_province | String | 源IP省份 |
| src_pos_city | String | 源IP城市 |
| src_pos_district | String | 源IP区县 |
| dst_pos_country | String | 目标IP国家 |
| dst_pos_province | String | 目标IP省份 |
| dst_pos_city | String | 目标IP城市 |
| dst_pos_district | String | 目标IP区县 |
| route_policy_id | UInt16 | 路由策略ID |
| malc_hit | UInt8 | 恶意命中标记 |
| vni | UInt32 | VNI |
| wan_name | String | WAN出口名称 |
⚠️ 查询必须带 start 时间条件；必须加 LIMIT

### dns — DNS查询日志（34亿条，大表）
| 列名 | 类型 | 说明 |
|------|------|------|
| dev_id | UInt16 | 设备ID |
| probe_id | UInt16 | 探针ID |
| collect_time | DateTime | 采集时间（时间分区键，必须带此条件） |
| src_mac | String | 源MAC |
| src_ipv4 | IPv4 | 源IPv4 |
| src_port | UInt16 | 源端口 |
| dst_ipv4 | IPv4 | 目标IPv4 |
| dst_port | UInt16 | 目标端口 |
| domain_name | String | 查询域名 |
| account | String | 用户账号 |
| src_ISP | String | 源ISP |
| dst_ISP | String | 目标ISP |
| src_pos_country | String | 源IP国家 |
| src_pos_province | String | 源IP省份 |
| src_pos_city | String | 源IP城市 |
| src_pos_district | String | 源IP区县 |
| dst_pos_country | String | 目标IP国家 |
| dst_pos_province | String | 目标IP省份 |
| dst_pos_city | String | 目标IP城市 |
| dst_pos_district | String | 目标IP区县 |
⚠️ 查询必须带 collect_time 时间条件；必须加 LIMIT

### url — HTTP/HTTPS访问日志（26亿条，大表）
| 列名 | 类型 | 说明 |
|------|------|------|
| dev_id | UInt16 | 设备ID |
| probe_id | UInt16 | 探针ID |
| ip_version | UInt8 | IP版本 |
| appid | UInt32 | 应用ID |
| collect_time | DateTime | 采集时间（时间分区键，必须带此条件） |
| src_mac | String | 源MAC |
| type | String | 请求类型 |
| uri | String | 请求URI |
| src_ipv4 | IPv4 | 源IPv4 |
| dst_ipv4 | IPv4 | 目标IPv4 |
| src_ipv6 | IPv6 | 源IPv6 |
| dst_ipv6 | IPv6 | 目标IPv6 |
| src_port | UInt16 | 源端口 |
| dst_port | UInt16 | 目标端口 |
| domain_name | String | 域名 |
| account | String | 用户账号 |
| accgrp_name | String | 账号组名 |
| src_ISP | String | 源ISP |
| dst_ISP | String | 目标ISP |
| src_pos_country | String | 源IP国家 |
| src_pos_province | String | 源IP省份 |
| src_pos_city | String | 源IP城市 |
| src_pos_district | String | 源IP区县 |
| dst_pos_country | String | 目标IP国家 |
| dst_pos_province | String | 目标IP省份 |
| dst_pos_city | String | 目标IP城市 |
| dst_pos_district | String | 目标IP区县 |
| vni | UInt32 | VNI |
⚠️ 查询必须带 collect_time 时间条件；必须加 LIMIT

### iplog — IP流量汇总（10亿条，60s聚合）
| 列名 | 类型 | 说明 |
|------|------|------|
| dev_id | UInt16 | 设备ID |
| probe_id | UInt16 | 探针ID |
| ip_version | UInt8 | IP版本 |
| collect_time | DateTime | 采集时间（时间分区键，必须带此条件） |
| interval | UInt32 | 统计间隔(s) |
| flowcnt | UInt16 | 流量数 |
| appid | UInt32 | 应用ID |
| natipcnt | UInt16 | NAT IP数 |
| up_bytes | UInt64 | 上行字节数 |
| down_bytes | UInt64 | 下行字节数 |
| account | String | 用户账号 |
| ipv4 | IPv4 | IP地址（注意：字段名是ipv4，不是src_ipv4） |
| ipv6 | IPv6 | IPv6地址 |
⚠️ 查询必须带 collect_time 时间条件；地址字段是 ipv4 不是 src_ipv4

### wanlog — WAN出口流量统计（119万条，60s聚合）
| 列名 | 类型 | 说明 |
|------|------|------|
| dev_id | UInt16 | 设备ID |
| probe_id | UInt16 | 探针ID |
| ip_version | UInt8 | IP版本 |
| collect_time | DateTime | 采集时间（时间分区键，必须带此条件） |
| interval | UInt32 | 统计间隔(s) |
| wan_id | UInt16 | WAN出口ID |
| wan_type | UInt8 | WAN出口类型 |
| in_bps | UInt64 | 入向速率(bps) |
| out_bps | UInt64 | 出向速率(bps) |
| ipv4 | IPv4 | IP地址 |
| ipv6 | IPv6 | IPv6地址 |
| wan_name | String | WAN出口名称 |
⚠️ 查询必须带 collect_time 时间条件；无 up_bytes/down_bytes 字段，流量用 in_bps/out_bps

### applog — 应用流量汇总（3330万条，60s聚合）
| 列名 | 类型 | 说明 |
|------|------|------|
| dev_id | UInt16 | 设备ID |
| probe_id | UInt16 | 探针ID |
| collect_time | DateTime | 采集时间（时间分区键，必须带此条件） |
| interval | UInt32 | 统计间隔(s) |
| flowcnt | UInt32 | 流量数 |
| appid | UInt32 | 应用ID |
| linkid | UInt16 | 链路ID |
| up_bytes | UInt64 | 上行字节数 |
| down_bytes | UInt64 | 下行字节数 |
⚠️ 查询必须带 collect_time 时间条件；无 up_pkts/down_pkts/src_ipv4/account 字段

### event — 应用事件日志（1.9亿条）
| 列名 | 类型 | 说明 |
|------|------|------|
| dev_id | UInt16 | 设备ID |
| probe_id | UInt16 | 探针ID |
| type | String | 事件类型(如 qqlogin3/weixin3/pop3login3) |
| ip_version | UInt8 | IP版本 |
| collect_time | DateTime | 采集时间（时间分区键，必须带此条件） |
| app_account | String | 应用账号 |
| src_ipv4 | IPv4 | 源IPv4 |
| dst_ipv4 | IPv4 | 目标IPv4 |
| src_ipv6 | IPv6 | 源IPv6 |
| dst_ipv6 | IPv6 | 目标IPv6 |
| src_port | UInt16 | 源端口 |
| dst_port | UInt16 | 目标端口 |
| account | String | 用户账号 |
| src_mac | String | 源MAC |
⚠️ 查询必须带 collect_time 时间条件

### usrauth — 用户认证记录（14万条）
| 列名 | 类型 | 说明 |
|------|------|------|
| dev_id | UInt16 | 设备ID |
| probe_id | UInt16 | 探针ID |
| ip_version | UInt8 | IP版本 |
| collect_time | DateTime | 采集时间（时间分区键，必须带此条件） |
| account | String | 用户账号 |
| src_ipv4 | IPv4 | 源IPv4 |
| src_ipv6 | IPv6 | 源IPv6 |
| src_mac | String | 源MAC |
| logtype | String | 认证类型(login/logoff) |
⚠️ 查询必须带 collect_time 时间条件

### axp — 应用名称映射表（小表，约数千行，无时间分区）
| 列名 | 类型 | 说明 |
|------|------|------|
| appid | UInt32 | 应用ID，与 sessions/npm/applog 的 appid 字段对应 |
| name | String | 应用英文名（如 http, bittorrent, youtube） |
| cname | String | 应用中文名（如 WWW, BitTorrent, YouTube） |
| root | UInt16 | 根分类ID |
| parent | UInt16 | 父分类ID |
| type | UInt8 | 应用类型 |
⚠️ axp 是小表，可以安全地与大表 JOIN；appid=0 表示"未知应用"

## 通用 SQL 规则
1. 所有查询必须包含时间条件（sessions/npm 用 start，其余用 collect_time）
2. 只允许 SELECT 语句
3. 大表（sessions/npm/dns/url）必须加 LIMIT，建议 10000
4. 时间范围超过7天时，按天分片查询
5. 严禁两个大表（sessions/npm/dns/url）相互 JOIN，会超时
6. 【应用名称】查询涉及 appid 时，必须 JOIN axp 表获取应用名称，在结果中展示 axp.cname（中文名）而非原始 appid 数字
   示例：SELECT a.cname AS app_name, count() AS cnt FROM sessions s LEFT JOIN axp a ON s.appid = a.appid WHERE ... GROUP BY a.cname ORDER BY cnt DESC LIMIT 10
"""
