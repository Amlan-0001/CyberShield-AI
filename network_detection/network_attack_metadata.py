ATTACK_INFO = {

    "Normal Traffic": {
        "risk_level": "Safe",
        "description": "Normal network traffic detected.",
        "recommendation": "No action required."
    },

    "DoS": {
        "risk_level": "High",
        "description": "Denial of Service attack detected.",
        "recommendation": "Enable rate limiting and block suspicious IP addresses."
    },

    "DDoS": {
        "risk_level": "Critical",
        "description": "Distributed Denial of Service attack detected.",
        "recommendation": "Block malicious IPs, inspect firewall logs, and enable DDoS protection."
    },

    "Port Scanning": {
        "risk_level": "Medium",
        "description": "Port scanning activity detected.",
        "recommendation": "Monitor the source IP and restrict unnecessary open ports."
    },

    "Brute Force": {
        "risk_level": "High",
        "description": "Brute force login attempt detected.",
        "recommendation": "Lock affected accounts and enforce strong passwords with MFA."
    },

    "Web Attacks": {
        "risk_level": "High",
        "description": "Web attack activity detected.",
        "recommendation": "Inspect web server logs and deploy Web Application Firewall rules."
    },

    "Bots": {
        "risk_level": "Medium",
        "description": "Bot traffic detected.",
        "recommendation": "Analyze bot behavior and apply filtering or CAPTCHA if required."
    }

}