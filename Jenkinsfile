pipeline {
    agent any

    environment {
        SWARM_MANAGER = credentials('docker-swarm-manager')
        DOCKER_REGISTRY = credentials('docker-registry')
        STACK_NAME = 'dividend-tracker'
        IMAGE_NAME = 'dividend-tracker-web'
    }

    stages {
        stage('Build') {
            steps {
                sh 'docker build -t ${DOCKER_REGISTRY}/${IMAGE_NAME}:latest .'
            }
        }

        stage('Push') {
            steps {
                sh 'docker push ${DOCKER_REGISTRY}/${IMAGE_NAME}:latest'
            }
        }

        stage('Deploy') {
            steps {
                sshagent(['jenkins-ssh']) {
                    sh '''
                        scp -o StrictHostKeyChecking=no docker-compose.yml jenkins@${SWARM_MANAGER}:/tmp/${STACK_NAME}-compose.yml
                        ssh -o StrictHostKeyChecking=no jenkins@${SWARM_MANAGER} "
                            export DOCKER_REGISTRY=${DOCKER_REGISTRY} &&
                            docker stack deploy -c /tmp/${STACK_NAME}-compose.yml ${STACK_NAME} &&
                            rm /tmp/${STACK_NAME}-compose.yml
                        "
                    '''
                }
            }
        }
    }

    post {
        failure {
            echo 'Deployment failed'
        }
        success {
            echo 'Deployment successful'
        }
    }
}
