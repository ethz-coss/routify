package ch.routify;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

import ch.routify.graph.CustomVertexFactory;

/**
 * The Routify class configures and starts the Routify application in local Docker mode.
 * This application provides routing services with air quality, noise, and green space
 * considerations for the Zurich area. All services run locally using Docker containers.
 * 
 * <p>The application uses the following local services:
 * <ul>
 *   <li>Photon geocoding service for address resolution</li>
 *   <li>Nominatim database for geocoding data</li>
 *   <li>Air quality service for PM10 data</li>
 *   <li>Local backend API for routing calculations</li>
 * </ul>
 * 
 * @author aeggerth@ethz.ch
 */
@SpringBootApplication
@EnableScheduling
public class Routify {
    /**
     * Local API configuration - no external domains needed for local Docker setup
     */
    public static final String url_api = "http://localhost:8080";

    /**
     * URL of the geocoder service. Using local Photon service in Docker.
     */
	public static final String url_geocoder = "photon:2322";

    /**
     * URL of the air quality service. Using local air quality service in Docker.
     */
    public static final String url_airquality = "http://airqualityservice:8000/get_pm10";
    
    /**
     * The logger used for logging information and development mode status.
     */
    public static final Logger logger = LoggerFactory.getLogger(Routify.class);

	/**
     * Indicates whether the application is running in development mode. This mode can affect
     * various runtime behaviors, such as logging and data preloading.
     */
    public static boolean developmentMode = false;

	/**
     * The main system component responsible for application initialization and functionality.
     */
    public static RoutifySystem sys;

	/**
     * Factory for creating custom vertexes as part of the application's data processing.
     */
    public static CustomVertexFactory vertexFactory = new CustomVertexFactory();

    /**
     * Logs the current configuration for local Docker setup.
     */
    private static void logConfiguration() {
        logger.info("Running in local Docker mode");
        logger.info("API URL: {}", url_api);
        logger.info("Geocoder URL: {}", url_geocoder);
        logger.info("Air quality URL: {}", url_airquality);
    }

    /**
     * Main method to start the Routify application in local Docker mode.
     * Initializes the system components and starts the Spring Boot application.
     * All services are configured to use local Docker containers.
     * 
     * @param args Command-line arguments. Use --devmode for development mode.
     * @throws Exception if there is an issue initializing the application or its components.
     */
	public static void main(String[] args) throws Exception {
        // Check for --devmode argument
        for (String arg : args) {
            if ("--devmode".equals(arg)) {
                developmentMode = true;
                break;
            }
        }

        // Log configuration for local Docker setup
        logConfiguration();

        sys = new RoutifySystem();
		sys.initialize();
        SpringApplication.run(Routify.class, args);
    }

	/**
     * Checks if the application is running in development mode.
     * 
     * @return {@code true} if the application is in development mode, {@code false} otherwise.
     */
    public static boolean devMode() {
        return developmentMode;
    }
}