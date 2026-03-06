pipeline {
    agent any

    environment {
        DOCKER_REGISTRY    = 'ancaotrinh'
        BACKEND_IMAGE      = "${DOCKER_REGISTRY}/phobert-backend"
        PREDICTOR_IMAGE    = "${DOCKER_REGISTRY}/phobert-medical-predictor"
        COVERAGE_THRESHOLD = '80'
    }

    stages {

        // ══════════════════════════════════════════════════════════════
        // STAGE 1 — Test Backend
        // ══════════════════════════════════════════════════════════════
        stage('Test Backend') {
            agent {
                docker {
                    image 'python:3.11-slim'
                    reuseNode true
                }
            }
            steps {
                dir('backend') {
                    sh '''
                        pip install -r requirements.txt
                        python -m pytest tests/ \
                            --cov=app \
                            --cov-report=xml:coverage.xml \
                            --cov-report=html:htmlcov \
                            --cov-report=term-missing \
                            --cov-fail-under=${COVERAGE_THRESHOLD} \
                            --junitxml=test-results.xml
                    '''
                }
            }
        }

        // ══════════════════════════════════════════════════════════════
        // STAGE 2 — Test Predictor
        // ══════════════════════════════════════════════════════════════
        stage('Test Predictor') {
            agent {
                docker {
                    image 'python:3.11-slim'
                    reuseNode true
                }
            }
            steps {
                dir('predictor') {
                    sh '''
                        pip install -r requirements.txt
                        python -m pytest tests/ \
                            --cov=app \
                            --cov-report=xml:coverage.xml \
                            --cov-report=html:htmlcov \
                            --cov-report=term-missing \
                            --cov-fail-under=${COVERAGE_THRESHOLD} \
                            --junitxml=test-results.xml
                    '''
                }
            }
        }

        // ══════════════════════════════════════════════════════════════
        // STAGE 3 — Check Coverage summary
        // ══════════════════════════════════════════════════════════════
        stage('Check Coverage') {
            agent {
                docker {
                    image 'python:3.11-slim'
                    reuseNode true
                }
            }
            steps {
                script {
                    def getCoverage = { path ->
                        sh(
                            script: """
                                python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('${path}/coverage.xml')
root = tree.getroot()
coverage = float(root.get('line-rate', 0)) * 100
print(f'{coverage:.1f}')
"
                            """,
                            returnStdout: true
                        ).trim().toDouble()
                    }

                    def backendCov   = getCoverage('backend')
                    def predictorCov = getCoverage('predictor')

                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "📊 Coverage Summary"
                    echo "   Backend:   ${backendCov}%"
                    echo "   Predictor: ${predictorCov}%"
                    echo "   Threshold: ${COVERAGE_THRESHOLD}%"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

                    if (backendCov < COVERAGE_THRESHOLD.toDouble()) {
                        error("❌ Backend coverage ${backendCov}% < ${COVERAGE_THRESHOLD}%")
                    }
                    if (predictorCov < COVERAGE_THRESHOLD.toDouble()) {
                        error("❌ Predictor coverage ${predictorCov}% < ${COVERAGE_THRESHOLD}%")
                    }
                    echo "✅ Coverage passed — proceeding to build"
                }
            }
        }

        // ══════════════════════════════════════════════════════════════
        // STAGE 4 — Build Docker Images
        // ══════════════════════════════════════════════════════════════
        stage('Build Docker Images') {
            steps {
                sh '''
                    docker build \
                        -t ${BACKEND_IMAGE}:${BUILD_NUMBER} \
                        -t ${BACKEND_IMAGE}:latest \
                        -f backend/Dockerfile backend/

                    docker build \
                        -t ${PREDICTOR_IMAGE}:${BUILD_NUMBER} \
                        -t ${PREDICTOR_IMAGE}:latest \
                        -f predictor/Dockerfile predictor/

                    echo "✅ Images built:"
                    echo "   ${BACKEND_IMAGE}:${BUILD_NUMBER}"
                    echo "   ${PREDICTOR_IMAGE}:${BUILD_NUMBER}"
                '''
            }
        }

        // ══════════════════════════════════════════════════════════════
        // STAGE 5 — Push to Registry
        // ══════════════════════════════════════════════════════════════
        stage('Push to Registry') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh '''
                        echo "${DOCKER_PASS}" | docker login -u "${DOCKER_USER}" --password-stdin
                        docker push ${BACKEND_IMAGE}:${BUILD_NUMBER}
                        docker push ${BACKEND_IMAGE}:latest
                        docker push ${PREDICTOR_IMAGE}:${BUILD_NUMBER}
                        docker push ${PREDICTOR_IMAGE}:latest
                        docker logout
                        echo "✅ Images pushed"
                    '''
                }
            }
        }

        // ══════════════════════════════════════════════════════════════
        // STAGE 6 — Manual Approval
        // ══════════════════════════════════════════════════════════════
        stage('Approval for Deploy') {
            steps {
                script {
                    def userInput = input(
                        id: 'DeployApproval',
                        message: "🚀 Deploy build #${BUILD_NUMBER} lên môi trường nào?",
                        ok: 'Deploy',
                        submitter: 'admin',
                        parameters: [
                            choice(
                                name: 'DEPLOY_ENV',
                                choices: ['production', 'staging'],
                                description: 'Chọn môi trường deploy'
                            )
                        ]
                    )
                    env.DEPLOY_ENV = userInput
                    echo "✅ Deploy approved — environment: ${env.DEPLOY_ENV}"
                }
            }
        }

        // ══════════════════════════════════════════════════════════════
        // STAGE 7 — Deploy with Helm
        // Mount kubeconfig từ Jenkins home vào container
        // Chạy: docker cp config.yaml jenkins:/var/jenkins_home/kubeconfig.yaml
        // ══════════════════════════════════════════════════════════════
        stage('Deploy with Helm') {
            agent {
                docker {
                    image 'dtzar/helm-kubectl:3.14'
                    reuseNode true
                    args '--entrypoint="" -v /var/jenkins_home/kubeconfig.yaml:/root/.kube/config'
                }
            }
            steps {
                script {
                    def backendNs = env.DEPLOY_ENV == 'production' ? 'ingress-nginx' : 'staging'
                    def modelNs   = env.DEPLOY_ENV == 'production' ? 'model-serving'  : 'model-serving-staging'

                    echo "🚀 Deploying to ${env.DEPLOY_ENV}"
                    echo "   Backend namespace:   ${backendNs}"
                    echo "   Predictor namespace: ${modelNs}"

                    sh """
                        helm upgrade --install phobert-backend \
                            ./helm/charts/backend \
                            --namespace ${backendNs} \
                            --create-namespace \
                            -f helm/charts/backend/values.yaml \
                            --set image.tag=${BUILD_NUMBER} \
                            --wait --timeout 10m

                        helm upgrade --install phobert-inference \
                            ./helm/charts/phobert-inference \
                            --namespace ${modelNs} \
                            --create-namespace \
                            -f helm/charts/phobert-inference/values.yaml \
                            --set image.tag=${BUILD_NUMBER} \
                            --wait --timeout 15m

                        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        echo "✅ Deployed to ${env.DEPLOY_ENV}!"
                        echo "   Backend:   ${BACKEND_IMAGE}:${BUILD_NUMBER}"
                        echo "   Predictor: ${PREDICTOR_IMAGE}:${BUILD_NUMBER}"
                        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        kubectl get pods -n ${backendNs} -l app=phobert-backend
                        kubectl get pods -n ${modelNs} -l app=phobert-inference
                    """
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: '**/test-results.xml'
            script {
                try {
                    publishHTML([
                        allowMissing: true,
                        alwaysLinkToLastBuild: false,
                        keepAll: true,
                        reportDir: 'backend/htmlcov',
                        reportFiles: 'index.html',
                        reportName: 'Backend Coverage Report'
                    ])
                    publishHTML([
                        allowMissing: true,
                        alwaysLinkToLastBuild: false,
                        keepAll: true,
                        reportDir: 'predictor/htmlcov',
                        reportFiles: 'index.html',
                        reportName: 'Predictor Coverage Report'
                    ])
                } catch (err) {
                    echo "⚠️ publishHTML skipped: htmlpublisher plugin chưa cài — ${err.message}"
                }
            }
        }
        success { echo '✅ Pipeline thành công!' }
        failure { echo '❌ Pipeline thất bại!' }
        aborted { echo '⏸️ Pipeline bị hủy tại stage Approval.' }
    }
}