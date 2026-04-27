// ======================================================
// Jenkinsfile - AIOps IoT Monitoring
// ======================================================
// Demonstration artifact showing Jenkins pipeline equivalent
// of the GitHub Actions workflow above.
//
// To run this for real:
//   1. Install Jenkins locally (docker run -p 8080:8080 jenkins/jenkins:lts)
//   2. Create a Pipeline job, point it at this repo
//   3. Jenkins will pick up this Jenkinsfile automatically
//
// Free-tier note: GitHub Actions (.github/workflows/ci.yml)
// is the live CI/CD pipeline. This Jenkinsfile demonstrates
// the same stages in Jenkins syntax for portfolio purposes.
// ======================================================

pipeline {
    agent any

    environment {
        PYTHON_VERSION = '3.11'
        DOCKER_IMAGE   = 'aiops-iot-monitoring'
        DOCKER_HUB_USR = credentials('dockerhub-username')
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                echo "Branch: ${env.BRANCH_NAME} | Commit: ${env.GIT_COMMIT[0..7]}"
            }
        }

        stage('Setup Python') {
            steps {
                sh 'python --version'
                sh 'pip install -r requirements.txt --quiet'
            }
        }

        stage('Lint') {
            steps {
                sh '''
                    pip install flake8 --quiet
                    flake8 backend/ --max-line-length=120 --ignore=E501,W503 || true
                '''
            }
        }

        stage('Unit Tests') {
            environment {
                DATABASE_URL = 'sqlite:///./jenkins_test.db'
                JWT_SECRET   = 'jenkins-ci-secret'
            }
            steps {
                sh '''
                    python -m pytest tests/unit tests/integration \
                        -v --tb=short \
                        --ignore=tests/agent_validation \
                        --junitxml=test-results.xml \
                        -x
                '''
            }
            post {
                always {
                    junit 'test-results.xml'
                    sh 'rm -f jenkins_test.db'
                }
            }
        }

        stage('Build Docker Image') {
            when { branch 'main' }
            steps {
                sh "docker build -t ${DOCKER_IMAGE}:${env.GIT_COMMIT[0..7]} -f Dockerfile ."
                sh "docker build -t ${DOCKER_IMAGE}-dashboard:${env.GIT_COMMIT[0..7]} -f Dockerfile.streamlit ."
            }
        }

        stage('Push to Docker Hub') {
            when { branch 'main' }
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-creds',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh '''
                        echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
                        docker tag ${DOCKER_IMAGE}:${GIT_COMMIT:0:7} ${DOCKER_USER}/${DOCKER_IMAGE}:latest
                        docker push ${DOCKER_USER}/${DOCKER_IMAGE}:latest
                    '''
                }
            }
        }

        stage('Cleanup') {
            steps {
                sh "docker image prune -f || true"
                cleanWs()
            }
        }
    }

    post {
        success {
            echo "Pipeline succeeded. Images pushed to Docker Hub."
        }
        failure {
            echo "Pipeline FAILED. Check logs above."
        }
    }
}
