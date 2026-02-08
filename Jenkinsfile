@Library('jenkins-sentinel') _

pipeline {
    agent any

    triggers {
        githubPush()
    }

    environment {
        DOCKER_REGISTRY = '192.168.1.23:5000'
        IMAGE_NAME = 'dividend-tracker'
        APP_NAME = 'dividend-tracker'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    withCredentials([usernamePassword(
                        credentialsId: 'docker-registry-credentials',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )]) {
                        sh '''#!/bin/bash
                            set -e
                            echo "Building Docker image..."
                            docker build -t ${DOCKER_REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} .
                            docker tag ${DOCKER_REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} ${DOCKER_REGISTRY}/${IMAGE_NAME}:latest
                        '''
                    }
                }
            }
        }

        stage('Push to Registry') {
            steps {
                script {
                    withCredentials([usernamePassword(
                        credentialsId: 'docker-registry-credentials',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )]) {
                        sh '''#!/bin/bash
                            set -e
                            echo "Pushing to registry..."
                            echo "${DOCKER_PASS}" | docker login ${DOCKER_REGISTRY} -u "${DOCKER_USER}" --password-stdin
                            docker push ${DOCKER_REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}
                            docker push ${DOCKER_REGISTRY}/${IMAGE_NAME}:latest
                        '''
                    }
                }
            }
        }

        stage('Deploy to k3s') {
            steps {
                script {
                    withCredentials([
                        file(credentialsId: 'k3s-kubeconfig', variable: 'KUBECONFIG'),
                        string(credentialsId: 'alpha-vantage-key', variable: 'ALPHA_VANTAGE_KEY')
                    ]) {
                        sh '''#!/bin/bash
                            set -e
                            echo "=== Deploying ${APP_NAME} to k3s ==="

                            # Create secret if it doesn't exist
                            if ! kubectl get secret dividend-tracker-secrets -n default >/dev/null 2>&1; then
                                echo "Creating secrets..."
                                kubectl create secret generic dividend-tracker-secrets \
                                    --from-literal=alpha-vantage-key="${ALPHA_VANTAGE_KEY:-}" \
                                    --from-literal=secret-key="$(openssl rand -hex 32)" \
                                    -n default
                            else
                                echo "Secrets already exist, skipping creation"
                            fi

                            # Apply MongoDB resources first (if not already deployed)
                            echo "Deploying MongoDB..."
                            kubectl apply -f kubernetes/mongodb-pvc.yaml
                            kubectl apply -f kubernetes/mongodb-service.yaml
                            kubectl apply -f kubernetes/mongodb-deployment.yaml

                            # Wait for MongoDB to be ready
                            echo "Waiting for MongoDB to be ready..."
                            kubectl wait --for=condition=ready pod -l app=dividend-tracker-mongodb -n default --timeout=120s || true

                            # Substitute BUILD_NUMBER in deployment.yaml
                            export BUILD_NUMBER=${BUILD_NUMBER}
                            envsubst < kubernetes/deployment.yaml | kubectl apply -f -

                            # Apply service and ingress
                            kubectl apply -f kubernetes/service.yaml
                            kubectl apply -f kubernetes/ingress.yaml

                            # Wait for rollout to complete
                            echo "Waiting for deployment to complete..."
                            kubectl rollout status deployment/${APP_NAME} -n default --timeout=5m

                            # Verify deployment
                            echo ""
                            echo "=== Deployment Summary ==="
                            kubectl get pods -l app=${APP_NAME} -n default
                            kubectl get pods -l app=dividend-tracker-mongodb -n default
                            kubectl get svc ${APP_NAME} -n default
                            kubectl get svc mongodb -n default
                            kubectl get ingress ${APP_NAME} -n default
                        '''
                    }
                }
            }
        }

        stage('Verify Health') {
            steps {
                script {
                    withCredentials([file(credentialsId: 'k3s-kubeconfig', variable: 'KUBECONFIG')]) {
                        sh '''#!/bin/bash
                            set -e
                            echo "=== Verifying Application Health ==="

                            # Wait for pods to be ready
                            kubectl wait --for=condition=ready pod -l app=${APP_NAME} -n default --timeout=60s

                            # Get pod name
                            POD_NAME=$(kubectl get pod -l app=${APP_NAME} -n default -o jsonpath='{.items[0].metadata.name}')
                            echo "Pod: $POD_NAME"

                            # Test health endpoint from within cluster
                            echo "Testing health endpoint..."
                            kubectl exec -n default $POD_NAME -- wget -q -O- http://localhost:5000/finance/health || echo "Health check warning (non-fatal)"

                            echo ""
                            echo "=== Deployment Complete ==="
                            echo "Access at: http://home.home/finance/"
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            sh '''
                docker rmi ${DOCKER_REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} || true
                docker rmi ${DOCKER_REGISTRY}/${IMAGE_NAME}:latest || true
            '''
        }
        success {
            echo '=== Deployment Successful! ==='
            echo "Application URL: http://home.home/finance/"
        }
        failure {
            echo '=== Deployment Failed! ==='
            echo 'Troubleshooting:'
            echo "1. Check app pods: kubectl get pods -l app=${APP_NAME} -n default"
            echo "2. Check MongoDB pods: kubectl get pods -l app=dividend-tracker-mongodb -n default"
            echo "3. Check logs: kubectl logs -l app=${APP_NAME} -n default"
            echo "4. Check MongoDB logs: kubectl logs -l app=dividend-tracker-mongodb -n default"
            echo "5. Check events: kubectl get events --sort-by=.lastTimestamp -n default"

            notifySentinel()
        }
    }
}
