#!/bin/bash
# AutoHeal AI - Incident Simulation Script
# Simulates various incident types for testing the AutoHeal system

set -e

MONITORING_URL="${MONITORING_URL:-http://localhost:8000}"
INCIDENT_MANAGER_URL="${INCIDENT_MANAGER_URL:-http://localhost:8002}"

echo "======================================"
echo "AutoHeal AI - Incident Simulation"
echo "======================================"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to simulate error rate spike
simulate_error_rate_spike() {
    echo ""
    echo -e "${YELLOW}Simulating error rate spike for payment-service...${NC}"
    
    curl -s -X POST "${INCIDENT_MANAGER_URL}/api/v1/events/anomaly" \
        -H "Content-Type: application/json" \
        -d '{
            "event_id": "sim-'"$(date +%s)"'",
            "timestamp": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'",
            "source_service": "monitoring",
            "anomaly_type": "error_rate_spike",
            "severity": "high",
            "target_service": "payment-service",
            "target_namespace": "production",
            "metric_name": "error_rate",
            "current_value": 0.15,
            "threshold_value": 0.05,
            "threshold_direction": "above",
            "metric_window_seconds": 300,
            "additional_context": {
                "simulated": true,
                "description": "Simulated error rate spike for testing"
            }
        }' | jq .
    
    echo -e "${GREEN}✅ Error rate spike simulated${NC}"
}

# Function to simulate latency spike
simulate_latency_spike() {
    echo ""
    echo -e "${YELLOW}Simulating latency spike for checkout-service...${NC}"
    
    curl -s -X POST "${INCIDENT_MANAGER_URL}/api/v1/events/anomaly" \
        -H "Content-Type: application/json" \
        -d '{
            "event_id": "sim-'"$(date +%s)"'-lat",
            "timestamp": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'",
            "source_service": "monitoring",
            "anomaly_type": "latency_spike",
            "severity": "medium",
            "target_service": "checkout-service",
            "target_namespace": "production",
            "metric_name": "latency_p99_ms",
            "current_value": 2500,
            "threshold_value": 1000,
            "threshold_direction": "above",
            "metric_window_seconds": 300,
            "additional_context": {
                "simulated": true,
                "percentile": "p99"
            }
        }' | jq .
    
    echo -e "${GREEN}✅ Latency spike simulated${NC}"
}

# Function to simulate CPU overload
simulate_cpu_overload() {
    echo ""
    echo -e "${YELLOW}Simulating CPU overload for api-gateway...${NC}"
    
    curl -s -X POST "${INCIDENT_MANAGER_URL}/api/v1/events/anomaly" \
        -H "Content-Type: application/json" \
        -d '{
            "event_id": "sim-'"$(date +%s)"'-cpu",
            "timestamp": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'",
            "source_service": "monitoring",
            "anomaly_type": "cpu_overload",
            "severity": "high",
            "target_service": "api-gateway",
            "target_namespace": "production",
            "metric_name": "cpu_percent",
            "current_value": 95,
            "threshold_value": 80,
            "threshold_direction": "above",
            "metric_window_seconds": 300,
            "additional_context": {
                "simulated": true
            }
        }' | jq .
    
    echo -e "${GREEN}✅ CPU overload simulated${NC}"
}

# Function to check service health
check_services() {
    echo ""
    echo "Checking service health..."
    
    # Check monitoring service
    if curl -s "${MONITORING_URL}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Monitoring service is healthy${NC}"
    else
        echo -e "${RED}❌ Monitoring service is not responding${NC}"
    fi
    
    # Check incident manager
    if curl -s "${INCIDENT_MANAGER_URL}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Incident Manager is healthy${NC}"
    else
        echo -e "${RED}❌ Incident Manager is not responding${NC}"
    fi
}

# Function to show current anomalies
show_anomalies() {
    echo ""
    echo "Current anomalies:"
    curl -s "${MONITORING_URL}/api/v1/anomalies" | jq .
}

# Main menu
show_menu() {
    echo ""
    echo "Select simulation type:"
    echo "  1) Error Rate Spike"
    echo "  2) Latency Spike"
    echo "  3) CPU Overload"
    echo "  4) All (run all simulations)"
    echo "  5) Check Services Health"
    echo "  6) Show Current Anomalies"
    echo "  7) Exit"
    echo ""
}

# Main loop
main() {
    while true; do
        show_menu
        read -p "Enter choice [1-7]: " choice
        
        case $choice in
            1) simulate_error_rate_spike ;;
            2) simulate_latency_spike ;;
            3) simulate_cpu_overload ;;
            4)
                simulate_error_rate_spike
                sleep 1
                simulate_latency_spike
                sleep 1
                simulate_cpu_overload
                ;;
            5) check_services ;;
            6) show_anomalies ;;
            7) 
                echo "Goodbye!"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option${NC}"
                ;;
        esac
    done
}

# Run with argument or interactive mode
if [ "$1" == "--all" ]; then
    check_services
    simulate_error_rate_spike
    sleep 2
    simulate_latency_spike
    sleep 2
    simulate_cpu_overload
    echo ""
    echo "All simulations complete!"
elif [ "$1" == "--check" ]; then
    check_services
else
    main
fi
