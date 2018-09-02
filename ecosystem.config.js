module.exports = {
  /**
   * Application configuration section
   * http://pm2.keymetrics.io/docs/usage/application-declaration/
   */
  apps : [

    // First application
    {
      name      : 'exraider',
      script    : 'pipenv run start',
      env: {
      },
      env_production : {
        NODE_ENV: 'production'
      }
    },
  ],

  /**
   * Deployment section
   * http://pm2.keymetrics.io/docs/usage/deployment/
   */
  deploy : {
    production : {
      user : 'ubuntu',
      host : 'u.r35.net',
      ref  : 'origin/master',
      repo : 'git@github.com:r35krag0th/exraidbot.git',
      path : '/home/ubuntu/workspace/bots/exraidbot',
      'pre-setup': 'pip install pipenv',
      'post-deploy' : 'pipenv install && cp -p /home/ubuntu/.config/bots/exraidbot/exraid.json config/exraid.json && pm2 reload ecosystem.config.js --env production'
    }
  }
};
