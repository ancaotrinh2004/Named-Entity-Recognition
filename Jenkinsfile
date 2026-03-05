pipeline {
    agent any

    environment {
        DOCKER_REGISTRY = 'ancaotrinh'
        BACKEND_IMAGE   = "${DOCKER_REGISTRY}/phobert-backend"
        PREDICTOR_IMAGE = "${DOCKER_REGISTRY}/phobert-medical-predictor"
        COVERAGE_THRESHOLD = '80'
    }

    stages {

        // ══════════════════════════════════════════════════════════════
        // STAGE 1 — Test Backend
        // Chạy pytest + fail ngay nếu coverage < 80%
        // ══════════════════════════════════════════════════════════════
        stage('Test Backend') {
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
        // STAGE 3 — Check Coverage (đọc từ coverage.xml đã generate)
        // Stage này chỉ để log + summary, việc fail đã do --cov-fail-under
        // ══════════════════════════════════════════════════════════════
        stage('Check Coverage') {
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

                    // Double-check — fail nếu thấp hơn threshold
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
        // Chỉ chạy nếu cả 2 coverage pass
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
        // Fix: thêm docker login với credentials
        // ══════════════════════════════════════════════════════════════
        stage('Push to Registry') {
            steps {
                // Cần tạo credential trong Jenkins:
                // Manage Jenkins → Credentials → Add → Username/Password
                // ID: dockerhub-credentials
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-credentials',
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
                        echo "✅ Images pushed to Docker Hub"
                    '''
                }
            }
        }

        // ══════════════════════════════════════════════════════════════
        // STAGE 6 — Manual Approval (trigger thủ công)
        // ══════════════════════════════════════════════════════════════
        stage('Approval for Deploy') {
            steps {
                script {
                    input(
                        id: 'DeployApproval',
                        message: "🚀 Deploy build #${BUILD_NUMBER} lên production?",
                        ok: 'Deploy',
                        submitter: 'jenkins-deployers',
                        parameters: [
                            choice(
                                name: 'DEPLOY_ENV',
                                choices: ['production', 'staging'],
                                description: 'Deploy environment'
                            )
                        ]
                    )
                    echo "✅ Deploy approved"
                }
            }
        }

        // ══════════════════════════════════════════════════════════════
        // STAGE 7 — Deploy with Helm
        // ══════════════════════════════════════════════════════════════
        stage('Deploy with Helm') {
            steps {
                sh '''
                    # ── Deploy Backend ──────────────────────────────
                    echo "🚀 Deploying Backend..."
                    helm upgrade --install phobert-backend \
                        ./helm/charts/backend \
                        --namespace api-gateway \
                        --create-namespace \
                        -f helm/charts/backend/values.yaml \
                        --set image.tag=${BUILD_NUMBER} \
                        --wait \
                        --timeout 10m

                    echo "✅ Backend deployed"
                    kubectl get pods -n api-gateway -l app=phobert-backend

                    # ── Deploy Predictor ─────────────────────────────
                    echo "🚀 Deploying Predictor..."
                    helm upgrade --install phobert-inference \
                        ./helm/charts/phobert-inference \
                        --namespace model-serving \
                        --create-namespace \
                        -f helm/charts/phobert-inference/values.yaml \
                        --set image.tag=${BUILD_NUMBER} \
                        --wait \
                        --timeout 15m

                    echo "✅ Predictor deployed"
                    kubectl get pods -n model-serving -l app=phobert-inference

                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "✅ All deployments completed!"
                    echo "   Backend:   ${BACKEND_IMAGE}:${BUILD_NUMBER}"
                    echo "   Predictor: ${PREDICTOR_IMAGE}:${BUILD_NUMBER}"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    kubectl get svc -n api-gateway -l app=phobert-backend
                    kubectl get svc -n model-serving -l app=phobert-inference
                '''
            }
        }
    }

    // ══════════════════════════════════════════════════════════════════
    // POST — luôn publish test results và coverage report
    // ══════════════════════════════════════════════════════════════════
    post {
        always {
            junit allowEmptyResults: true, testResults: '**/test-results.xml'

            // Fix: thêm --cov-report=html ở test stage để có htmlcov/
            publishHTML([
                allowMissing: true,
                reportDir: 'backend/htmlcov',
                reportFiles: 'index.html',
                reportName: 'Backend Coverage Report'
            ])
            publishHTML([
                allowMissing: true,
                reportDir: 'predictor/htmlcov',
                reportFiles: 'index.html',
                reportName: 'Predictor Coverage Report'
            ])
        }
        success {
            echo '✅ Pipeline thành công!'
        }
        failure {
            echo '❌ Pipeline thất bại! Kiểm tra logs bên trên.'
        }
        aborted {
            echo '⏸️ Pipeline bị hủy tại stage Approval.'
        }
    }
}