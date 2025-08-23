module.exports = {
  apps: [
    {
      name: 'all-strategies',
      script: 'python3',
      args: 'scripts/run_all_strategies.py',
      cwd: '/Users/justincoit/crypto-tracker-v3',
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 100,
      min_uptime: '10s',
      max_memory_restart: '500M',
      error_file: 'logs/pm2-strategies-error.log',
      out_file: 'logs/pm2-strategies-out.log',
      log_file: 'logs/pm2-strategies-combined.log',
      time: true
    },
    {
      name: 'data-collector',
      script: 'python3',
      args: 'scripts/run_data_collector.py',
      cwd: '/Users/justincoit/crypto-tracker-v3',
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 100,
      min_uptime: '10s',
      max_memory_restart: '500M',
      error_file: 'logs/pm2-collector-error.log',
      out_file: 'logs/pm2-collector-out.log',
      log_file: 'logs/pm2-collector-combined.log',
      time: true
    },
    {
      name: 'paper-trading',
      script: 'python3',
      args: 'scripts/run_paper_trading.py',
      cwd: '/Users/justincoit/crypto-tracker-v3',
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 100,
      min_uptime: '10s',
      max_memory_restart: '500M',
      error_file: 'logs/pm2-trading-error.log',
      out_file: 'logs/pm2-trading-out.log',
      log_file: 'logs/pm2-trading-combined.log',
      time: true
    }
  ]
};
