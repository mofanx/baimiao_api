module.exports = {
  apps: [
    {
      name: 'baimiao-ocr-api',
      script: 'uvicorn',
      args: 'api_server:app --host 0.0.0.0 --port 8000',
      interpreter: 'python',
      cwd: __dirname,
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: 'logs/baimiao-error.log',
      out_file: 'logs/baimiao-out.log',
      merge_logs: true,
      env: {
        BAIMIAO_API_KEY: process.env.BAIMIAO_API_KEY
      }
    }
  ]
};
