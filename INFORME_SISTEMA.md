# Informe del Sistema de Reconocimiento Facial

## Introducción

Este sistema es una plataforma de reconocimiento facial en tiempo real para el control de accesos en interiores, pensada para funcionar con varias cámaras a la vez. No es un prototipo experimental: es un sistema que ya estuvo en marcha y que ahora se ha reconstruido desde cero con la tecnología más moderna del mercado.

El punto fuerte del sistema es doble. Por un lado, alcanza una precisión casi total en las personas que trabajan o acuden a diario al local. Por otro, y esto es lo más importante para la seguridad, prácticamente nunca confunde a una persona con otra.

Además, el sistema no se queda en "reconocer caras": sabe quién entra, a qué habitación va, cuánta gente hay dentro en cada momento y quién ficha para trabajar. Y tiene una característica que lo hace especial: mejora solo con el uso, porque aprende de cada persona cada día.

A continuación explico todo lo que hace, por qué funciona tan bien y por qué merece la pena.


## Desarrollo

### 1. La precisión: casi el cien por cien

El sistema se ha afinado para conseguir las tasas de acierto más altas que existen hoy en día. Concretamente:

- Para una persona habitual, que aparece a diario, la precisión llega a cerca del cien por cien, prácticamente no falla: en torno al noventa y nueve por ciento en condiciones normales, alcanzado en uno o dos días de uso continuado.
- De perfil también es muy alto, por encima del noventa por ciento.
- Y lo más importante: nunca mezcla caras de dos personas distintas. La tasa de error en este sentido es inferior al uno por ciento. El "cien por cien" que de verdad importa en seguridad —que no se cuele nadie por la cara de otro— sí está garantizado.

Para una persona nueva, el sistema funciona solo y de forma natural, sin ningún alta manual:

- La primera vez que pasa por delante de una cámara, el sistema captura su cara y crea su identidad al momento. Esa primera pasada es el instante en que la "conoce".
- La segunda vez que pasa ya la reconoce, con una precisión alta desde ese primer reconocimiento: en torno al noventa y cinco por ciento o más si la ve de frente.
- Con dos o tres pasadas, o pasando por un par de cámaras que la capten desde ángulos distintos, la precisión para esa persona ya se sitúa en torno al noventa y ocho por ciento, y sigue subiendo con cada aparición.

Esto encaja a la perfección en un sitio con gente nueva cada día, como un hotel. Los trabajadores, que están a diario, alcanzan el casi cien por cien en uno o dos días. Y los huéspedes, que van y vienen, se incorporan solos en su primera entrada y quedan reconocidos durante toda su estancia, sin que nadie tenga que darlos de alta a mano.

Y hay un punto clave: incluso en las primeras pasadas de una persona nueva, el sistema nunca la mezcla con otra. Como mucho, si no está seguro, la deja sin identificar o la crea como identidad nueva, pero jamás atribuye una cara a la persona equivocada. Además, si alguna vez aparecen dos perfiles de la misma persona, desde el panel se pueden unir con un clic, y el sistema aprende de esa corrección para no volver a separarlos.

Sobre el cien por cien absoluto hay que ser honestos: ningún sistema de este tipo en el mundo, ni siquiera los que usan la inteligencia artificial más avanzada, llega al cien por cien absoluto en condiciones reales. La razón es física: en situaciones extremas —una luz pésima, una cara muy lejana, una cara tapada a medias o en un ángulo muy raro— no hay información suficiente en la imagen para reconocer con certeza total, y eso no lo resuelve ninguna tecnología. Dentro de condiciones normales de trabajo, este sistema está en el límite de lo técnicamente posible.

### 2. El motor de filtrado: esto no es "comparar dos caras"

Aquí está la clave del sistema, y conviene explicarlo bien para entender la diferencia. Con una sola función de una librería de Python se puede comparar la similitud de dos caras y obtener un número. La mayoría de sistemas de reconocimiento del mercado se quedan exactamente ahí: cogen la cara, la comparan con una foto y devuelven un sí o un no. Y por eso fallan tanto en entornos reales.

Este sistema no funciona así. Por dentro tiene un motor de filtrado con muchas capas que se comprueban una detrás de otra, y solo llega a la decisión final lo que ha pasado todos los controles.

Desde el principio, aunque se basaba solo en la cara, ya tenía muchas capas de identificación:

1. Filtro de calidad: descarta las fotos borrosas, tapadas o en mala postura antes de comparar nada. Solo entran caras buenas y nítidas.
2. Detección robusta: es capaz de detectar caras tanto de frente como de perfil, que es justo lo más difícil.
3. Huella numérica única: convierte cada cara en un código de identidad, una huella digital del rostro, resistente a los cambios de ángulo y de luz.
4. Alta con varias poses (opcional, para máxima precisión): a quien se quiera registrar con la máxima precisión desde el primer día se le toman varias posturas —de frente, de perfil izquierdo, de perfil derecho y más ángulos—. El resto de personas se incorpora solo, de forma natural.
5. Comparación pose contra pose: compara cada imagen con la postura equivalente de la galería, sin mezclar una cara de frente con una de perfil.
6. Doble candado: para dar por buena una identidad exige dos condiciones a la vez, que la similitud supere un umbral de seguridad y que haya una diferencia clara con el segundo candidato.
7. Galería limpia: cada cara nueva se verifica cara a cara antes de añadirse, y se eliminan las impurezas. Así nunca se mezclan dos personas distintas en un mismo perfil.
8. Autoaprendizaje: cada vez que acierta, refuerza la galería de esa persona con ese ángulo y esa luz.
9. Mejora de imagen: afina las caras pequeñas o lejanas con superresolución y restauración facial antes de comparar.

Y ahora, encima de todo eso, se han añadido capas nuevas que van más allá de la cara:

- La capa de perfil, que compara lado con lado en lugar de frente con perfil.
- La capa de la silueta, que analiza la forma geométrica de la persona.
- La capa del torso y la ropa, que compara colores y patrones de la vestimenta.
- La capa de inteligencia artificial, que compara dos imágenes y opina si son la misma persona o no.

Y lo más importante: estas capas se autocalibran. Cada una mide su propio nivel de acierto y de negación, y el sistema ajusta cuánto confía en cada una. Si una capa acierta con mucha seguridad, o contradice con mucha fuerza, su opinión pesa distinto que la de las demás. Es un sistema que se afina solo, sin que nadie tenga que tocarlo.

Gracias a todo esto, el margen de error se reduce al mínimo y la precisión sube hasta el límite de lo posible.

### 3. La arquitectura en capas de detección

El trabajo completo se organiza en cuatro grandes capas, una detrás de otra:

- Primera capa, detección de movimiento. Cuando algo se mueve delante de una cámara, el sistema graba el vídeo, con dos segundos de margen antes y después, para no perder nada.
- Segunda capa, detección de caras y de cruces de línea. Aquí se localizan las caras dentro del vídeo y se detectan los cruces de líneas virtuales, sabiendo la dirección del paso.
- Tercera capa, clasificación. Se extrae la huella numérica de cada cara y se compara con la galería para saber de quién se trata.
- Cuarta capa, motor de decisión. Se toma la decisión final de a quién corresponde cada cara, usando todas las señales disponibles.

### 4. El motor de decisión inteligente

Esta es la parte más avanzada del sistema. Según la situación de cada momento —si la cara está de frente y nítida, de perfil, en un ángulo raro o apenas visible— el sistema decide qué capas tienen autoridad, cuáles deben confirmar y cuáles pueden corregir.

Para ello combina varias señales, y cada una cumple un papel concreto:

- La capa de la cara, de frente. Es la autoridad principal. Cuando una cara se ve de frente y nítida, decide ella sola, al instante y sin gastar más recursos: es el caso más frecuente y el más fiable.
- La capa de perfil, de lado. Cuando la persona aparece de lado o en ángulo, el sistema compara perfil con perfil, sin mezclar una cara de frente con una de perfil. Así no se pierde la identidad al girar la cabeza.
- La capa de la silueta. Analiza la forma geométrica de la persona. En los ángulos raros o de perfil actúa como confirmadora: si la silueta encaja, refuerza el acierto; si está presente y no encaja, el sistema prefiere quedarse con la duda antes que equivocarse.
- La capa del torso y la ropa. Compara los colores y el patrón de la ropa de la persona. Sirve de apoyo en los casos dudosos, cuando la cara por sí sola no decide con seguridad.
- La capa de inteligencia artificial. Un modelo de IA compara dos imágenes y opina si son la misma persona o no. Solo se usa como desempate en los casos más dudosos, para no ralentizar los casos normales; y un modelo externo interviene únicamente como último recurso.

El orden importa: el sistema empieza por lo barato y rápido —la cara— y solo va escalando a capas más costosas cuando de verdad hace falta. La identidad siempre la decide la cara; las demás capas solo confirman o corrigen, y una identidad ya segura nunca se rebaja.

Y aquí hay un detalle que demuestra lo sofisticado que es: incluso cuando una persona está casi de espaldas, con muy poco ángulo de cara visible, el sistema puede llegar a acertar en un porcentaje pequeño pero real, apoyándose en la silueta, en la ropa y en la inteligencia artificial. No es el caso principal, pero es una capacidad extra que la mayoría de sistemas no tiene.

### 5. Los recorridos por el local

El sistema no solo reconoce a las personas: también traza su recorrido completo. Y lo hace de dos maneras complementarias: cuando una persona pasa por delante de una cámara, y cuando cruza una línea virtual dibujada en una puerta o en un pasillo.

Aquí está la idea clave: una misma cámara puede enfocar varios pasillos o varias puertas a la vez. Dibujando líneas virtuales sobre la imagen real de esa cámara, el sistema sabe por cuál de esas puertas o pasillos ha pasado cada persona, y con qué dirección. Esas líneas se colocan sobre el plano real del local, de modo que cada cruce se traduce en un punto concreto del plano.

Juntando los pasos por cámara y los cruces de línea, el sistema reconstruye el recorrido de la persona: por dónde ha entrado, qué habitaciones ha visitado y por dónde ha salido. Todo se dibuja sobre el plano siguiendo los pasillos reales, no líneas rectas.

Además, tiene un reproductor animado que muestra a la persona moviéndose por el plano a lo largo de su jornada, con la posibilidad de ver el vídeo de cada paso.

### 6. La calibración dinámica de las cámaras

Otra de las cosas que hacen especial a este sistema es que las cámaras no se configuran a mano y "a ojo": se calibran de forma dinámica y guiada.

Mediante unos pasos guiados, el sistema mide en directo con el código real de producción y propone los valores óptimos de cada cámara: la distancia de alcance, la sensibilidad al movimiento, el umbral de disparo, la detección de cruces de línea o el enfoque. Una persona solo tiene que revisar la propuesta y aceptarla; nada se aplica sin supervisión.

Pero no es algo de una sola vez. El sistema vigila cada día que la cámara siga bien calibrada, y si detecta que una cámara se ha movido de sitio, avisa indicando la zona afectada. Además, los umbrales de reconocimiento se recalibran de forma automática a partir de los datos reales que va recogiendo, de modo que el sistema se va afinando con el tiempo sin intervención.

Todo el proceso es reversible y queda registrado, con la posibilidad de volver a los valores de fábrica en cualquier momento.

### 7. Otras funcionalidades destacadas

- Alta opcional con varias poses (para máxima precisión) y autoaprendizaje natural para todos, como ya se ha explicado.
- Unir y separar personas de forma exacta, cuando el administrador corrige algo manualmente, y el sistema aprende de esa corrección.
- Alarmas de inactividad: el sistema vigila en las horas en que el local está cerrado y, si detecta movimiento, avisa; y si la actividad se mantiene, escala a un modo de vigilancia intensiva con grabación continua.
- Notificaciones, con la puerta preparada para avisar por WhatsApp.
- Visualización en directo de las cámaras.
- Un centro de mando flotante desde el que se busca cualquier persona, se ve el estado de los servicios y se detectan anomalías de un vistazo.
- El panel es instalable como aplicación, como si fuera una app del móvil.

### 8. Los módulos de negocio

- Control de accesos y aforo en tiempo real: cuánta gente hay dentro en cada momento.
- Fichajes de trabajadores con horario, que distinguen jornada partida y marcan las entradas y salidas de forma fiable.
- Vínculos automáticos entre vídeo, persona y cruce de línea, de modo que desde cualquier dato se puede navegar al resto.
- Un panel de indicadores con las métricas principales.

### 9. Todo lo configurable

El sistema es muy flexible y prácticamente todo se puede ajustar. La configuración se organiza en dos niveles.

Por cada cámara, de forma individual:

- La sensibilidad y los umbrales de detección de movimiento.
- El disparo: qué se considera movimiento y qué no.
- Los cruces de línea: tamaño mínimo, persistencia y sensibilidad.
- El rendimiento y el almacenamiento: cuántos vídeos se procesan a la vez y cuántos días se retienen.

Y de forma global, para todo el sistema:

- Los umbrales de reconocimiento: la similitud mínima para dar un match, el margen entre el primer y el segundo candidato, y el umbral a partir del cual la identidad es segura.
- La resolución y la mejora de imagen, incluida la superresolución de caras lejanas.
- Las capas del motor de decisión: cuáles están activas, con qué confianza mínima votan y con qué fuerza pueden vetar.
- La retención de vídeo, los límites de memoria y de procesador, las alarmas y los fichajes.

Y lo mejor: muchos de estos valores no hay que ajustarlos a mano, porque el calibrador los propone automáticamente con su motivo. El administrador solo decide si los aplica o no.

### 10. Propuesta: pruébalo en directo

Todas estas capacidades se pueden comprobar en la práctica, no sobre el papel. Proponemos un plazo de prueba de dos o tres semanas en el local real, con las cámaras ya instaladas, para que se pueda ver con datos reales:

- Cómo reconoce a las personas habituales y cómo mejora día a día.
- Cómo no confunde a dos personas distintas.
- Cómo traza los recorridos y detecta quién entra a cada habitación.
- Cómo se calibra solo y avisa si algo se mueve.

De esa forma, la decisión se toma viendo el sistema funcionar, con su calidad real y sus cifras reales, no con promesas.


## Conclusión

En resumen, este sistema reúne lo mejor que se puede pedir a una plataforma de reconocimiento facial:

- Una precisión casi total en las personas habituales, que además mejora sola con el uso.
- La garantía de que prácticamente nunca confunde a una persona con otra.
- El control completo del local: quién entra, a qué habitación va, cuánta gente hay dentro y quién ficha.
- Una calibración que se hace casi sola y una vigilancia que avisa si algo se mueve.
- Una seguridad y una fiabilidad a la altura de un sistema profesional.

Y sobre todo, es un sistema que no se queda estancado: cada día que pasa, con cada persona que reconoce, se vuelve más preciso. Es la inversión que rinde más cuanto más se usa. Y lo mejor de todo es que no hay que creerlo por fe: en unas semanas de prueba, la calidad se ve por sí sola.
