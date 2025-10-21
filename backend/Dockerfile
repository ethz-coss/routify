# Build stage
FROM maven:3.8.3-openjdk-17 AS build
ADD src /home/app/src
ADD pom.xml /home/app
WORKDIR /home/app
RUN mvn package -DskipTests

# Package stage
FROM openjdk:17-jdk-slim
COPY --from=build /home/app/target/*.jar routify-1.0.0.jar

# curl only for container healthcheck; remove if not needed
RUN apt-get update -y && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

EXPOSE 8080
ENTRYPOINT ["java","-jar","routify-1.0.0.jar"]
