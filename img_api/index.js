// Implementation of the photo-API used as example on RESTdesc.org

'use strict'

const crypto = require('crypto')

const _ = require('lodash')
const path = require('path')
const fs = require('fs-extra')
const bunyan = require('bunyan')
const express = require('express')
const { promisify } = require('util')
const { processenv } = require('processenv')
const fileUpload = require('express-fileupload')
const execFile = promisify(require('child_process').execFile)
const nunjucks = require('nunjucks')

// Instantiate logger
const log = bunyan.createLogger({
  name: 'img_api', // TODO make configurable?
  stream: process.stdout,
  level: processenv('IMG_API_LOGLEVEL', bunyan.INFO),
  serializers: {
    err: bunyan.stdSerializers.err,
    req: bunyan.stdSerializers.req,
    res: function (res) {
      if (!res || !res.statusCode) {
        return res
      }
      return {
        statusCode: res.statusCode,
        headers: res._headers
      }
    }
  }
})

const images = {}

// Read configuration
async function readConfig () {
  const config = {
    language: processenv('IMG_API_LANG', 'en'),
    tmpDirectory: processenv('IMG_API_TMP', '/tmp'),
    listenPort: processenv('IMG_API_PORT', 3000)
  }

  // Construct resource paths
  const lang = config.language
  const resourceNames = {
    images: {
      en: 'images',
      de: 'bilder',
      fr: 'photos'
    },
    thumbnail: {
      en: 'thumbnail',
      de: 'miniaturbild',
      fr: 'miniature'
    }
  }

  const collectionOfImages = `/${resourceNames.images[lang]}`
  const specificImage = `${collectionOfImages}/:imageId`
  const thumbnail = `${specificImage}/${resourceNames.thumbnail[lang]}`

  config.paths = {
    collectionOfImages: collectionOfImages,
    specificImage: specificImage,
    thumbnail: thumbnail
  }

  return config
}

// Perform actual work
async function resizeImage (original, resized, size) {
  await execFile('/usr/bin/convert', [original, '-resize', `x${size}`, resized])
  log.debug(`Resized file to a height of ${size} px (keeping the aspect ratio)`)
}

async function readResourceStateFromDisk (basePath) {
  await fs.ensureDir(basePath)
  const dirContents = await fs.readdir(basePath)

  for (const item of dirContents) {
    const itemPath = path.join(basePath, item)
    const itemProperties = await fs.stat(itemPath)

    if (!itemProperties.isDirectory()) {
      const fileName = _.last(_.split(itemPath, '/'))
      const buffer = await fs.readFile(itemPath)
      const hash = crypto
        .createHash('md5')
        .update(buffer)
        .digest('hex')

      // Update knowledge about resource state
      images[hash] = {
        fileName: fileName,
        filePath: itemPath
      }
    }
  }
}

// Describe hypermedia API using RESTdesc
async function n3addImage (req, res) {
  const host = _.get(req, ['headers', 'host'])
  const protocol = _.get(req, ['protocol'])
  const origin = `${protocol}://${host}`

  const cfg = await readConfig()
  const fileName = 'add_image_restdesc.n3.j2'

  const url = `${origin}${cfg.paths.collectionOfImages}`

  res.format({
    'text/n3': async function () {
      res.set('Allow', 'POST,HEAD,OPTIONS')
      res.set('Content-Type', 'text/n3')
      res.status(200).render(fileName, { path: url })
    },
    default: async function () {
      await respondWithNotAcceptable(req, res)
    }
  })
}

async function n3getImage (req, res) {
  await respondWithNotImplemented(req, res)
}

async function n3getThumbnail (req, res) {
  const fileName = 'get_thumbnail_restdesc.n3'

  res.format({
    'text/n3': async function () {
      res.set('Allow', 'GET,HEAD,OPTIONS')
      res.set('Content-Type', 'text/n3')
      res.status(200).render(fileName)
    },
    default: async function () {
      await respondWithNotAcceptable(req, res)
    }
  })
}

// Define request handlers
async function browseAPI (req, res) {
  await respondWithNotImplemented(req, res)
}

async function addImage (req, res) {
  const host = _.get(req, ['headers', 'host'])
  const protocol = _.get(req, ['protocol'])
  const origin = `${protocol}://${host}`

  const cfg = await readConfig()
  const baseDir = `${cfg.tmpDirectory}/images`

  // Create new identifier for image
  let fileName
  let buffer
  const multipartFieldName = 'image' // FIXME Communicate via RESTdesc!!
  try {
    fileName = req.files[multipartFieldName].name
    buffer = req.files[multipartFieldName].data
  } catch (error) {
    await respondWithBadRequest(req, res)
    return
  }
  const hash = crypto
    .createHash('md5')
    .update(buffer)
    .digest('hex')

  // Store file on disk
  const filePath = `${baseDir}/${hash}`
  const filePathExists = await fs.pathExists(filePath)

  if (!filePathExists) {
    await fs.ensureDir(baseDir)
    await fs.writeFile(filePath, buffer)
  }

  // Update knowledge about resource state
  images[hash] = {
    fileName: fileName,
    filePath: filePath
  }
  log.debug(`Added image \`${fileName}\` to API-instance as \`/images/${hash}\``)
  log.trace({ images: images })

  // Acknowlegde successfull addition
  const imagePath = _.replace(cfg.paths.specificImage, ':imageId', hash)
  const thumbnailPath = _.replace(cfg.paths.thumbnail, ':imageId', hash)
  res.format({
    'text/n3': async function () {
      res.set('Content-Type', 'text/n3')
      res.status(201).render('add_image_response.n3.j2', {
        image_id: fileName,
        thumbnail_url: `${origin}${thumbnailPath}`
      })
    },
    'application/ld+json': async function () {
      res.set('Content-Type', 'application/ld+json')
      res.status(201).render('add_image_response.jsonld.j2', {
        image_id: fileName,
        thumbnail_url: `${origin}${thumbnailPath}`
      })
    },
    default: async function () {
      await respondWithNotAcceptable(req, res)
    }
  })
}

async function getImage (req, res) {
  const hash = _.last(_.split(req.path, '/'))
  let file
  try {
    file = images[hash].filePath
  } catch (error) {
    await respondWithNotFound(req, res)
    return
  }

  res.format({
    'image/png': async function () {
      res.sendFile(file)
    },
    default: async function () {
      await respondWithNotAcceptable(req, res)
    }
  })
}

async function getThumbnail (req, res) {
  const host = _.get(req, ['headers', 'host'])
  const protocol = _.get(req, ['protocol'])
  const origin = `${protocol}://${host}`

  const hash = _.nth(_.split(req.path, '/'), -2)

  let filePath
  let fileName
  try {
    filePath = images[hash].filePath
    fileName = images[hash].fileName
  } catch (error) {
    await respondWithNotFound(req, res)
    return
  }

  const cfg = await readConfig()
  const baseDir = `${cfg.tmpDirectory}/thumbs`

  const thumbnail = `${baseDir}/${hash}`

  await fs.ensureDir(baseDir)
  await resizeImage(filePath, thumbnail, 80)

  res.format({
    'image/png': async function () {
      res.sendFile(thumbnail)
    },
    'text/n3': async function () {
      res.set('Content-Type', 'text/n3')
      res.status(200).render('get_thumbnail_response.n3.j2', {
        image_id: fileName,
        thumbnail_url: `${origin}${req.path}`
      })
    },
    'application/ld+json': async function () {
      res.set('Content-Type', 'application/ld+json')
      res.status(200).render('get_thumbnail_response.jsonld.j2', {
        image_id: fileName,
        thumbnail_url: `${origin}${req.path}`
      })
    },
    default: async function () {
      await respondWithNotAcceptable(req, res)
    }
  })
}

// Properly respond in case of errors
async function sendProblemDetail (res, config) {
  // `config` is a dictionary containing the fields from RFC 7807
  // field `status` is required; `detail`, `type`, `title`, `instance` are optional
  res.set('Content-Type', 'application/problem+json')
  const statusCode = config.status
  res.status(statusCode).json(config)
}

async function respondWithNotImplemented (req, res) {
  await sendProblemDetail(res, {
    title: 'Not Implemented',
    status: 501,
    detail:
      'The request was understood, but the underlying implementation is not available yet.'
  })
}

async function respondWithNotFound (req, res) {
  await sendProblemDetail(res, {
    title: 'Not Found',
    status: 404,
    detail: 'The requested resource was not found on this server'
  })
}

async function respondWithNotAcceptable (req, res) {
  await sendProblemDetail(res, {
    title: 'Not Acceptable',
    status: 406,
    detail: 'The requested (hyper-) media type is not supported for this resource'
  })
}

async function respondWithBadRequest (req, res) {
  await sendProblemDetail(res, {
    title: 'Bad Request',
    status: 400,
    detail: 'The request was malformed and the server refuses to process it'
  })
}

// Initialize server
async function init () {
  const cfg = await readConfig()
  log.debug({ config: cfg }, 'Instance configuration loaded')

  // Learn about images already available
  await readResourceStateFromDisk(`${cfg.tmpDirectory}/images`)

  // Instantiate express-application and set up middleware-stack
  const app = express()
  app.use(fileUpload())
  nunjucks.configure('templates', { autoescape: true, express: app })

  // Log every request
  app.use(async function (req, res, next) {
    log.debug(
      {
        request: {
          method: req.method,
          originalUrl: req.originalUrl
        }
      },
      `Received ${req.method}-request at ${req.originalUrl}`
    )
    next()
  })

  // Define routing
  app.get('/', browseAPI)

  app.options(cfg.paths.collectionOfImages, n3addImage)
  app.post(cfg.paths.collectionOfImages, addImage)

  app.options(cfg.paths.specificImage, n3getImage)
  app.get(cfg.paths.specificImage, getImage)

  app.options(cfg.paths.thumbnail, n3getThumbnail)
  app.get(cfg.paths.thumbnail, getThumbnail)

  // Send 404 as reaction to all other requests
  app.use((req, res, next) => respondWithNotFound(req, res, next))

  // Start listening to incoming requests
  app.listen(cfg.listenPort, function () {
    log.info(`Listening on port ${cfg.listenPort}`)
  })
}

// Run when executed as module
if (require.main === module) {
  init()
}
