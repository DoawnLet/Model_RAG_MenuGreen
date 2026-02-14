# Menu Green Monitoring Stack

This directory contains configuration for monitoring and observability.

## Components

### 1. Prometheus

- **Port**: 9090
- **Scrape interval**: 15s
- **Targets**: FastAPI app on localhost:8000

### 2. Grafana

- **Port**: 3001
- **Data source**: Prometheus
- **Dashboards**: Menu Green System Dashboard

## Quick Start

### Using Docker Compose

```bash
# Start monitoring stack
cd monitoring
docker-compose up -d

# View logs
docker-compose logs -f

# Stop monitoring
docker-compose down
```

### Manual Setup

#### Prometheus

```bash
# Download Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*

# Copy config
cp ../prometheus.yml ./

# Run
./prometheus --config.file=prometheus.yml
```

#### Grafana

```bash
# Download Grafana
wget https://dl.grafana.com/oss/release/grafana-10.0.0.linux-amd64.tar.gz
tar -zxvf grafana-*.tar.gz
cd grafana-*

# Run
./bin/grafana-server
```

## Accessing Services

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3001 (admin/admin)
- **Metrics endpoint**: http://localhost:8000/metrics

## Grafana Setup

1. Open Grafana: http://localhost:3001
2. Login with admin/admin (change password on first login)
3. Add Prometheus data source:
   - Configuration → Data Sources → Add data source
   - Select Prometheus
   - URL: http://prometheus:9090 (or http://localhost:9090 if not using Docker)
   - Save & Test
4. Import dashboard:
   - Dashboards → Import
   - Upload `grafana-dashboard.json`
   - Select Prometheus data source
   - Import

## Key Metrics

### HTTP Requests

- `menu_green_http_requests_total` - Total requests by endpoint and status
- `menu_green_http_request_duration_seconds` - Request latency

### LLM Calls

- `menu_green_llm_calls_total` - Total LLM calls by model and agent
- `menu_green_llm_call_duration_seconds` - LLM call latency
- `menu_green_llm_tokens_used_total` - Token consumption
- `menu_green_llm_cost_usd_total` - LLM costs in USD

### Agent Execution

- `menu_green_agent_executions_total` - Agent execution count
- `menu_green_agent_execution_seconds` - Agent execution time by intent

### RAG Search

- `menu_green_rag_searches_total` - RAG search count
- `menu_green_rag_search_duration_seconds` - RAG search latency

### Database

- `menu_green_db_queries_total` - Database query count
- `menu_green_db_query_duration_seconds` - Database query latency

### Cache

- `menu_green_memory_cache_hits_total` - Cache hit count
- `menu_green_memory_cache_misses_total` - Cache miss count
- `menu_green_memory_cache_size` - Current cache size

### Errors

- `menu_green_errors_total` - Error count by type and endpoint

### System Health

- `menu_green_system_health` - Health status (1=healthy, 0=unhealthy)

## Alerting

Configure alerts in Grafana or Prometheus AlertManager:

### Example Alerts

1. **High Error Rate**

   ```promql
   rate(menu_green_errors_total[5m]) > 0.1
   ```

2. **High LLM Costs**

   ```promql
   increase(menu_green_llm_cost_usd_total[1h]) > 1.0
   ```

3. **Database Unhealthy**

   ```promql
   menu_green_system_health == 0
   ```

4. **Slow Responses**
   ```promql
   histogram_quantile(0.95, rate(menu_green_http_request_duration_seconds_bucket[5m])) > 5
   ```

## Cost Tracking

Monitor LLM costs with queries:

```promql
# Total cost last 24h
increase(menu_green_llm_cost_usd_total[24h])

# Cost by model
sum by (model) (increase(menu_green_llm_cost_usd_total[1h]))

# Cost rate per minute
rate(menu_green_llm_cost_usd_total[1m]) * 60
```

## Performance Optimization

Use metrics to identify bottlenecks:

1. **Slowest Endpoints**:

   ```promql
   topk(5, histogram_quantile(0.95, rate(menu_green_http_request_duration_seconds_bucket[5m])))
   ```

2. **Slowest Agents**:

   ```promql
   topk(5, histogram_quantile(0.95, rate(menu_green_agent_execution_seconds_bucket[5m])))
   ```

3. **Cache Hit Rate**:
   ```promql
   menu_green_memory_cache_hits_total / (menu_green_memory_cache_hits_total + menu_green_memory_cache_misses_total)
   ```

## Troubleshooting

### Metrics not appearing

- Check FastAPI is running: http://localhost:8000/health
- Check metrics endpoint: http://localhost:8000/metrics
- Verify Prometheus is scraping: http://localhost:9090/targets

### Grafana not connecting

- Verify Prometheus data source URL
- Check Docker network if using containers
- Test with curl: `curl http://localhost:9090/api/v1/query?query=up`

## Production Deployment

For production:

1. **Secure Prometheus**: Add authentication
2. **Secure Grafana**: Use strong passwords, enable HTTPS
3. **Set up AlertManager**: Configure email/Slack notifications
4. **Remote storage**: Consider Prometheus remote write for long-term storage
5. **High availability**: Deploy Prometheus in HA mode
6. **Backup**: Regularly backup Grafana dashboards and Prometheus data

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)
