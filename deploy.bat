@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

:: 변수 설정
SET REGION=ap-northeast-2
SET ACCOUNT_ID=868615245439
SET REPO_NAME=equal/survey-service
SET ECR=%ACCOUNT_ID%.dkr.ecr.%REGION%.amazonaws.com
SET REGISTRY_REPO=%ECR%/%REPO_NAME%

:: 사용자로부터 프로젝트 버전 입력
set /p IMAGE_TAG="Please enter the project version (default is 'latest'): "
if "%IMAGE_TAG%"=="" set IMAGE_TAG=latest

:: Docker 이미지 빌드
docker build --no-cache -t %REGISTRY_REPO% .

:: ECR 로그인
FOR /F "tokens=*" %%i IN ('aws ecr get-login-password --region %REGION%') DO SET PASSWORD=%%i
docker login --username AWS --password !PASSWORD! %ECR%

:: 이미지에 리포지토리 태그 지정 및 푸시
if "%IMAGE_TAG%" neq "latest" (
    docker tag %REGISTRY_REPO%:latest %REGISTRY_REPO%:%IMAGE_TAG%
    docker push %REGISTRY_REPO%:%IMAGE_TAG%
)
docker push %REGISTRY_REPO%:latest

ENDLOCAL