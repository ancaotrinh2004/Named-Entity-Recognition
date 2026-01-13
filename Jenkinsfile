pipeline {
    agent any
    
    stages {
        stage('Test') {
            steps {
                echo 'Running tests...'
            }
        }
        
        stage('Build') {
            steps {
                echo 'Building Docker image...'
            }
        }
        
        stage('Deploy') {
            steps {
                input message: 'Deploy to production?'
                echo 'Deploying...'
            }
        }
    }
}