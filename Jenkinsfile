pipeline {
    agent any

    environment {
        DOCKER_REGISTRY = credentials('docker-registry')
        SWARM_MANAGER = credentials('docker-swarm-manager')
        IMAGE_NAME = 'dividend-tracker-web'
        IMAGE_TAG = "${BUILD_NUMBER}"
        STACK_NAME = 'dividend-tracker'
        SWARM_SSH_CREDENTIALS = 'jenkins-ssh'
    }

    stages {
        stage('Build') {
            steps {
                sh """
                    docker build \
                        --tag ${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} \
                        --tag ${DOCKER_REGISTRY}/${IMAGE_NAME}:latest \
                        .
                """
            }
        }

        stage('Push') {
            steps {
                script {
                    docker.withRegistry("http://${DOCKER_REGISTRY}") {
                        sh """
                            docker push ${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
                            docker push ${DOCKER_REGISTRY}/${IMAGE_NAME}:latest
                        """
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                sshagent(credentials: [SWARM_SSH_CREDENTIALS]) {
                    sh """
                        sed 's|\\\${DOCKER_REGISTRY}|${DOCKER_REGISTRY}|g' docker-compose.yml > /tmp/${STACK_NAME}-compose.yml
                        scp -o StrictHostKeyChecking=no /tmp/${STACK_NAME}-compose.yml jenkins@${SWARM_MANAGER}:/tmp/${STACK_NAME}-compose.yml
                        ssh -o StrictHostKeyChecking=no jenkins@${SWARM_MANAGER} '
                            docker stack deploy -c /tmp/${STACK_NAME}-compose.yml ${STACK_NAME}
                            rm /tmp/${STACK_NAME}-compose.yml
                        '
                        rm /tmp/${STACK_NAME}-compose.yml
                    """
                }
            }
        }

        stage('Verify') {
            steps {
                sshagent(credentials: [SWARM_SSH_CREDENTIALS]) {
                    sh """
                        ssh -o StrictHostKeyChecking=no jenkins@${SWARM_MANAGER} '
                            docker stack services ${STACK_NAME}
                        '
                    """
                }
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true'
        }
        failure {
            echo 'Deployment failed'
        }
        success {
            echo "Deployment successful: ${IMAGE_NAME}:${IMAGE_TAG}"
        }
    }
}
