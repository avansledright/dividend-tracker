pipeline {
    agent any

    environment {
        SWARM_MANAGER = credentials('docker-swarm-manager')
        STACK_NAME = 'dividend-tracker'
        IMAGE_NAME = 'dividend-tracker-web'
    }

    stages {
        stage('Build') {
            steps {
                sh 'docker build -t ${IMAGE_NAME}:latest .'
                sh 'docker save ${IMAGE_NAME}:latest | gzip > ${IMAGE_NAME}.tar.gz'
            }
        }

        stage('Transfer') {
            steps {
                sshagent(['jenkins-ssh']) {
                    sh '''
                        scp -o StrictHostKeyChecking=no ${IMAGE_NAME}.tar.gz jenkins@${SWARM_MANAGER}:/tmp/
                        scp -o StrictHostKeyChecking=no docker-compose.yml jenkins@${SWARM_MANAGER}:/tmp/${STACK_NAME}-compose.yml
                    '''
                }
            }
        }

        stage('Deploy') {
            steps {
                sshagent(['jenkins-ssh']) {
                    sh '''
                        ssh -o StrictHostKeyChecking=no jenkins@${SWARM_MANAGER} "
                            docker load < /tmp/${IMAGE_NAME}.tar.gz &&
                            docker stack deploy -c /tmp/${STACK_NAME}-compose.yml ${STACK_NAME} &&
                            rm /tmp/${IMAGE_NAME}.tar.gz /tmp/${STACK_NAME}-compose.yml
                        "
                    '''
                }
            }
        }
    }

    post {
        always {
            sh 'rm -f ${IMAGE_NAME}.tar.gz'
        }
        failure {
            echo 'Deployment failed'
        }
        success {
            echo 'Deployment successful'
        }
    }
}
