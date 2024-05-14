@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

:: 변수 설정
SET REGISTRY=dev.promptinsight.ai
SET REPO_NAME=dev/survey-service
SET REGISTRY_REPO=%REGISTRY%/%REPO_NAME%

:: 사용자로부터 프로젝트 버전 입력
SET /p IMAGE_TAG="Please enter the project version: "
IF "%IMAGE_TAG%"=="" (
    echo Error: No version input provided. Exiting...
    goto :eof
)

:: Docker 이미지 빌드
docker build --no-cache -t %REGISTRY_REPO% .

:: 이미지에 리포지토리 태그 지정 및 푸시
docker tag %REGISTRY_REPO%:latest %REGISTRY_REPO%:%IMAGE_TAG%
docker push %REGISTRY_REPO%:%IMAGE_TAG%
docker push %REGISTRY_REPO%:latest

ENDLOCAL